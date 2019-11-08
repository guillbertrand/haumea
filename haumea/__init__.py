import os
import re
import sys
import json
import time
import requests
import logging
import shutil
import argparse

try:
    __version__ = __import__('pkg_resources') \
        .get_distribution('haumea').version
except Exception:
    __version__ = "unknown"

##


class Template():
    def __init__(self, content):
        self.text = content

        toks = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", self.text)

        ops = []
        ops_stack = []
        for tok in toks:
            if tok.startswith('{{'):
                # Expression: ('exp', expr)
                ops.append(('exp', tok[2:-2].strip()))
            elif tok.startswith('{%'):
                # Action tag: split into words and parse further.
                words = tok[2:-2].strip().split()
                if words[0] == 'if':
                    # If: ('if', (expr, body_ops))
                    if_ops = []
                    assert len(words) == 2
                    ops.append(('if', (words[1], if_ops)))
                    ops_stack.append(ops)
                    ops = if_ops
                elif words[0] == 'include':
                    # Include: ('include', filename)
                    assert len(words) == 2
                    ops.append(('include', words[1]))
                elif words[0] == 'for':
                    # For: ('for', (varname, listexpr, body_ops))
                    assert len(words) == 4 and words[2] == 'in'
                    for_ops = []
                    ops.append(('for', (words[1], words[3], for_ops)))
                    ops_stack.append(ops)
                    ops = for_ops
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack
                    ops = ops_stack.pop()
                    assert ops[-1][0] == words[0][3:]
                elif words[0].startswith('menu'):
                    assert len(words) == 2
                    ops.append(('menu', words[1]))
                else:
                    logging.warning(
                        "\U0000270B  Don't understand tag %r" % words)
            else:
                ops.append(('lit', tok))

        if ops_stack:
            logging.error("\U0001F4A5  Unmatched action tag: %r" %
                          ops_stack[-1][0])

        self.ops = ops

    def render(self, context=None):
        engine = TemplateEngine(context)
        engine.execute(self.ops)
        return "".join(engine.result)

##


class TemplateEngine():
    def __init__(self, context):
        self.context = context
        self.result = []

    def execute(self, ops):
        for op, args in ops:
            if op == 'lit':
                self.result.append(args)
            elif op == 'exp':
                try:
                    self.result.append(str(self.evaluate(args)))
                except BaseException:
                    exc_class, exc, _ = sys.exc_info()
                    new_exc = exc_class("Couldn't evaluate {{ %s }}: %s"
                                        % (args, exc))
                    raise new_exc
            elif op == 'if':
                expr, body = args
                if self.evaluate(expr):
                    self.execute(body)
            elif op == 'for':
                var, lis, body = args
                vals = self.evaluate(lis)
                for val in vals:
                    self.context[var] = val
                    self.execute(body)
            elif op == 'include':
                filename = os.path.join(layout_path, args.replace('"', ''))
                tpl = Template(Haumea.get_file_contents(filename))
                self.result.append(tpl.render(self.context))
            elif op == 'menu':
                value = '<ul>'
                for m in self.context['_menus'][args]:
                    if 'nav_title' in m['page']._params:
                        t = m['page']._params['nav_title']
                    else:
                        t = m['page']._params['title']
                    value += '<li {2}><a {2} href="{0}">{1}</a></li>'.format(
                        m['page'].permalink, t,
                        'class="active"' if m['is_active'] else '')
                value += '</ul>'
                self.result.append(value)
            else:
                logging.warning("Template engine error with op %r" % op)

    def evaluate(self, expr):
        if "|" in expr:
            pipes = expr.split("|")
            value = self.evaluate(pipes[0])
            for func in pipes[1:]:
                value = func.format(value)
        elif "." in expr:
            dots = expr.split('.')
            value = self.evaluate(dots[0])
            for dot in dots[1:]:
                try:
                    value = getattr(value, dot)
                except AttributeError:
                    value = value[dot]
                if hasattr(value, '__call__'):
                    value = value()
        else:
            value = self.context[expr]
        return value

##


class Page():
    def __init__(self, filename, base_layout, json={}):
        self._json = json
        self.input_filename = filename
        self.basedirname = os.path.dirname(filename.replace(input_path, ''))
        self.basename = os.path.basename(filename)
        self.params_pattern = r"---(.*)---\n?"
        self.base_layout = base_layout

        self.raw_contents = Haumea.get_file_contents(self.input_filename)
        self.final_contents = re.sub(
            self.params_pattern, '', self.raw_contents, 0, re.DOTALL)

        self._params = self.get_params()

        self.load_data_from_json()
        self.render_params()

        self.output_filename = self.get_output_filename()
        self.output_dirname = os.path.dirname(self.output_filename)
        self.permalink = self.output_filename.replace(
            output_path, '/').replace('index.html', '')

    def get_output_filename(self):
        # index.html
        if self.basename == 'index.html':
            output_filename = os.path.join(
                output_path, self.basedirname, 'index.html')
        # slug with basename
        elif self.basename[0] != '_' and 'slug' not in self._params:
            output_filename = os.path.join(
                output_path, self.basedirname, os.path.splitext(
                    self.basename)[0], "index.html")
        # slug with params
        else:
            slug = str(self._params['slug']).replace(
                '/', '').replace(' ', '-')  # TODO slugify
            output_filename = os.path.join(
                output_path, self.basedirname, slug, "index.html")
        return output_filename

    def load_data_from_json(self):
        if not self._json and "json-source" in self._params:
            try:
                ts = time.time()

                source = self._params['json-source']
                payload = self._params['json-params'] if 'json-params' in self._params else ''
                headers = self._params['json-headers'] if 'json-headers' in self._params else ''
                root_node = self._params['json-root-node'] if 'json-root-node' in self._params else ''
                req_type = self._params['json-request-type'] if 'json-request-type' in self._params else 'get'

                if req_type == 'graphql':
                    gql_file = os.path.splitext(self.input_filename)[
                        0] + '.graphql'
                    if os.path.exists(gql_file):
                        logging.debug(
                            'GraphQL file find {:s}'.format(gql_file))
                        payload = {'query': Haumea.get_file_contents(gql_file)}
                        req_type = 'post'

                if req_type == 'post':
                    res = requests.post(source, json=payload, headers=headers)
                else:
                    res = requests.get(source, params=payload, headers=headers)

                if res.status_code == 200:
                    fields_dict = json.loads(res.text)
                    if root_node:
                        self._json = Haumea.get_data_from_json(
                            fields_dict, root_node)
                    else:
                        self._json = fields_dict
                    te = time.time()
                    logging.info(
                        'Load json \U0001F52D  - {:s} request -'
                        ' {:2.2f}ms : {:.80}...'.format(req_type, (te - ts) * 1000, source))
                    logging.debug('{:s}'.format(res.text))
            except BaseException:
                logging.error(
                    '\U0001F4A5  Unable to load json file {:.80}'.format(source))

    def get_params(self):
        result = {}
        matches = re.finditer(self.params_pattern,
                              self.raw_contents, re.DOTALL)
        for matchNum, match in enumerate(matches, start=1):
            yml = match.group(1)
            result = json.loads(yml)
        return result

    def render_params(self):
        if "json-source" in self._params:
            for p_key, p_value in self._params.items():
                if isinstance(p_value, str) and p_value.startswith('{{'):
                    try:
                        tpl = Template(p_value)
                        self._params[p_key] = tpl.render({'_json': self._json})
                    except BaseException:
                        pass

    def get_menus(self):
        result = []
        if 'menus' in self._params:
            result = self._params['menus']
        return result

    def render(self, menus):
        amenus = {}
        for k, m in menus.items():
            amenus[k] = []
            for i in m:
                active = (i[0].permalink == self.permalink)
                amenus[k].append({'page': i[0], 'is_active': active})

        data = {
            '_menus': amenus,
            '_json': self._json,
            '_params': self._params
        }
        content = Template(self.final_contents).render(data)

        data['_content'] = content
        return Template(self.base_layout).render(data)

#


class PageBundle(Page):
    def __init__(self, path, base_layout):
        Page.__init__(self, path, base_layout)

    def get_pages(self):
        pages = []
        for i in self._json:
            page = Page(self.input_filename, self.base_layout, i)
            pages.append(page)
        return pages

##


class Haumea:

    def __init__(self, logging_level=logging.INFO):
        self.logging_level = logging_level
        self.menus = {}
        self.pages = []
        self.layout_base = Haumea.get_file_contents(
            os.path.join(layout_path, '_base.html'))

    @staticmethod
    def get_file_contents(filename):
        contents = ''
        try:
            f = open(filename, "r")
            if f.mode == 'r':
                contents = f.read()
            f.close()
        except BaseException:
            logging.error(
                '\U0001F4A5  Unable to load file {:.80}'.format(filename))
        return contents

    @staticmethod
    def get_data_from_json(json_data, json_path):
        res = ''
        basenode = ''
        for key in json_path.split("."):
            matches = re.findall(r"(\[(\d+)\])", key, re.DOTALL)
            arr = ''
            for m in matches:
                arr += ('[%s]' % m[1])
                key = key.replace(m[0], '')
            basenode += '["%s"]' % key
            basenode = basenode + arr if arr else basenode
        try:
            res = eval("json_data%s" % basenode)
        except BaseException:
            pass
        return res

    def add(self, page):
        # add menus
        for menu in page.get_menus():
            menu_items = menu.split(':')
            m = menu_items[0]
            weight = 0 if len(menu_items) != 2 else menu_items[1]
            if m in self.menus:
                self.menus[m].append([page, weight])
            else:
                self.menus[m] = [[page, weight]]

        # sort menus
        for key, menu in self.menus.items():
            self.menus[key] = sorted(menu, key=lambda val: int(val[1]))

        # add pages
        self.pages.append(page)

    def build(self):

        FORMAT = '* %(levelname)s - %(message)s'
        logging.basicConfig(level=self.logging_level, format=FORMAT)
        logger = logging.getLogger('Haumea')
        logger.info('\U0001F680  Haumea %s - Start build \U0001F680' %
                    __version__)

        # scan dir
        for root, subdirs, files in os.walk(input_path):

            # file
            for filename in files:
                fn = os.path.join(root, filename)
                # static page
                if os.path.splitext(filename)[1] == '.html' and filename[0] != '_':
                    page = Page(fn, self.layout_base)
                    self.add(page)
                # page bundle
                elif os.path.splitext(filename)[1] == '.html' and filename[0] == '_':
                    page_bundle = PageBundle(fn, self.layout_base).get_pages()
                    for page in page_bundle:
                        self.add(page)

        # clean output path
        try:
            shutil.rmtree(output_path)
            logger.info('Clean output path : %s' % output_path)
        except BaseException:
            logger.warning('Unable to clean output path : %s' % output_path)

        # copy static assets
        try:
            shutil.copytree(static_path, os.path.join(
                output_path, static_path.replace(static_path, '')))
            logger.info('Copy static directory : %s' % static_path)
        except BaseException:
            logger.warning('Unable to copy static assets : %s' % static_path)

        ts = time.time()
        # write files
        for page in self.pages:
            if not os.path.exists(page.output_dirname):
                os.makedirs(page.output_dirname)
            f = open(page.output_filename, "w")
            f.write(page.render(self.menus))
            f.close()
            logger.info('\U00002728  Render page \U0001F527  %s' %
                        (page.output_filename.replace(working_dir, '')))

        te = time.time()
        nb = len(self.pages)
        tt = (te - ts) * 1000
        me = tt / nb
        logger.info(
            '\U0001F331  %d pages built in %2.2f ms (%2.2fms/pp) \U0001F30D ' %
            (nb, tt, me))

#


def haumea_parse_args():
    parser = argparse.ArgumentParser(
        description='Haumea Static Site Generator',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("action",
                        default="build",
                        help="Action : build, serve")
    parser.add_argument('-p', '--port', default=8000, type=int, nargs="?",
                        help="Port to Listen On")
    parser.add_argument('-o', '--output', default='public/',
                        help='Where to output the generated files. If not '
                        'specified, a directory will be created, named '
                        '"public" in the current path.')
    parser.add_argument('-d', '--debug', action='store_const',
                        default=logging.INFO,
                        const=logging.DEBUG, dest='verbosity',
                        help='Show all messages, including debug messages.')
    parser.add_argument('-q', '--quiet', action='store_const',
                        default=logging.INFO,
                        const=logging.CRITICAL, dest='verbosity',
                        help='Show only critical errors.')
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=__version__,
        help='Print the version')
    return parser.parse_args()

#


working_dir = os.getcwd()
input_path = os.path.join(working_dir, 'content/')
output_path = os.path.join(working_dir, 'public/')
layout_path = os.path.join(working_dir, 'layouts/')
static_path = os.path.join(working_dir, 'static/')


def main():
    global output_path
    args = haumea_parse_args()
    action = args.action
    if args.output:
        output_path = os.path.join(working_dir, args.output)

    h = Haumea(args.verbosity)

    if action == "build":
        h.build()

    if action == "serve":
        h.build()
        os.system(
            "python3 -m http.server --bind 127.0.0.1 --directory %s" %
            output_path)
