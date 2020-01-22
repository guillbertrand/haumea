import os
import re
import sys
import ssl
import json
import time
import requests
import logging
import shutil
import argparse
import threading

from dateutil.parser import parse
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from http.server import HTTPServer, SimpleHTTPRequestHandler

_QUICKSTART_PATH = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    'quickstart'
)

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
        for i, tok in enumerate(toks):
            # Escape '''
            if (i-1) >= 0 and toks[i-1].strip().endswith("'EXPR"):
                ops.append(('lit', tok))
                continue
            if tok.startswith('{{'):
                # Expression: ('exp', expr)
                ops.append(('exp', tok[2:-2].strip()))
            elif tok.startswith('{%'):
                # Action tag: split into words and parse further.
                words = tok[2:-2].strip().split()
                if words[0] == 'if':
                    # If: ('if', (expr, body_ops))
                    if_ops = []
                    assert len(words) >= 2 or len(words) <= 4
                    ops.append(('if', (words, if_ops)))
                    ops_stack.append(ops)
                    ops = if_ops
                elif words[0] == 'haumea':
                    # Render Haumea version
                    assert len(words) == 1
                    ops.append(('haumea', words))
                elif words[0] == 'include':
                    # Include: ('include', filename)
                    assert len(words) == 2
                    ops.append(('include', words[1]))
                elif words[0] == 'pagination':
                    assert len(words) == 1 or len(words) == 2
                    ops.append(('pagination', words))
                elif words[0] == 'for':
                    # For: ('for', (varname, listexpr, body_ops, slice))
                    assert (len(words) == 4 or len(words) == 5) and words[2] == 'in'
                    for_ops = []
                    if len(words) == 4:
                        words.append(None)
                    ops.append(('for', (words[1], words[3], for_ops, words[4])))
                    ops_stack.append(ops)
                    ops = for_ops
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack
                    ops = ops_stack.pop()
                    assert ops[-1][0] == words[0][3:]
                elif words[0].startswith('menu'):
                    assert len(words) == 2 or len(words) == 3
                    ops.append(('menu', words))
                elif words[0].startswith('time'):
                    assert len(words) == 1
                    ops.append(('time', words[0]))
                elif words[0].startswith('link'):
                    assert len(words) == 2
                    ops.append(('link', words[1]))
                else:
                    logging.warning(
                        "\U0000270B  Don't understand tag %r" % words)
            else:
                ops.append(('lit', tok.replace("'EXPR", "")))

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
                if len(expr) == 2:
                    if self.evaluate(expr[1]):
                        self.execute(body)
                elif len(expr) == 3 and expr[1] == "not":
                    if not self.evaluate(expr[2]):
                        self.execute(body)
                elif len(expr) == 4:
                    res = eval('("%s" %s %s)' % (self.evaluate(expr[1]), expr[2], expr[3]))
                    if res:
                        self.execute(body)
            elif op == 'for':
                var, lis, body, slice_str = args
                vals = self.evaluate(lis)
                if(slice_str):
                    slice_item = slice_str.split(':')
                    slice_res = [int(slice_item[i]) if i < len(slice_item) and slice_item[i] else None for i in range(3)]
                    vals = vals[slice(*slice_res)]
                for val in vals:
                    self.context[var] = val
                    self.execute(body)
            elif op == 'include':
                filename = os.path.join(layout_path, args.replace('"', ''))
                tpl = Template(Haumea.get_file_contents(filename))
                self.result.append(tpl.render(self.context))
            elif op == 'haumea':
                self.result.append(__version__)
            elif op == 'pagination':
                filename = '_pagination.html' if len(args) == 1 else args[1]
                filename = os.path.join(layout_path, filename.replace('"', ''))
                tpl = Template(Haumea.get_file_contents(filename))
                if len(self.context['_pagination']['pages']) > 1:
                    self.result.append(tpl.render({'pagination': self.context['_pagination']}))
            elif op == 'menu':
                value = ''
                node = {0: ['a', '', ''], 1: ['li', '', ''], 2: ['ul', '', '']}
                params = reversed(args[2].split('>')) if len(args) == 3 else []
                if(params):
                    node = {0: ['']*3, 1: ['']*3, 2: ['']*3}
                    for i, mp in enumerate(params):
                        for ii, val in enumerate(mp.split('.')):
                            node[i][ii] = val
                # wrap menu
                if node[2][0]:
                    value += '<%s%s>' % (node[2][0], ' class="%s"' % node[2][1] if node[2][1] else '')
                for m in self.context['_menus'][args[1]]:
                    item_class, str_class = [], ''
                    title = m['page'].p('nav-title') if m['page'].p('nav-title') else m['page'].p('title')
                    # wrap node
                    if node[1][0]:
                        value += '<%s%s>' % (node[1][0], ' class="%s"' % node[1][1] if node[1][1] else '')
                    # item class
                    if node[0][1]:
                        item_class.append(node[0][1])
                    if node[0][2] and m['is_active']:
                        item_class.append(node[0][2])
                    if len(item_class):
                        str_class = ' class="%s"' % ' '.join(item_class)
                    # item
                    value += '<{0}{1} href="{2}">{3}</{0}>'.format(
                            node[0][0],
                            str_class,
                            m['page'].permalink,
                            title)
                    if node[1][0]:
                        value += '</%s>' % (node[1][0])
                if node[0][0]:
                    value += '</%s>' % (node[0][0])
                self.result.append(value)
            elif op == 'time':
                self.result.append(str(time.time()))
            elif op == 'link':
                link = ''
                link_args = args.replace('"', '').strip("/").split('#')
                anchor = '#%s' % link_args[1] if len(link_args) == 2 else ''
                if link_args[0] in self.context['_pages']:
                    link = '%s' % self.context['_pages'][link_args[0]].permalink
                self.result.append('%s%s' % (link, anchor))
            else:
                logging.warning("Template engine error with op %r" % op)

    def evaluate(self, expr):
        if "|" in expr:
            pipes = expr.split("|")
            value = self.evaluate(pipes[0])
            for func in pipes[1:]:
                try:
                    value = func.format(value)
                except ValueError:
                    value = parse(value)
                    value = func.format(value)
        elif "." in expr:
            dots = expr.split('.')
            value = self.evaluate(dots[0])
            for dot in dots[1:]:
                if dot.startswith('#'):
                    if dot.replace('#', '') in self.context['_json']:
                        dot = self.context['_json'][dot.replace('#', '')]
                    elif dot.replace('#', '') in self.context['_params']:
                        dot = self.context['_params'][dot.replace('#', '')]
                try:
                    value = getattr(value, dot)
                except AttributeError:
                    try:
                        dotint = int(dot)
                        value = value[dotint]
                    except ValueError:
                        try:
                            value = value[dot]
                        except KeyError:
                            value = ''

                if hasattr(value, '__call__'):
                    value = value()
        else:
            value = self.context[expr]
        return value

##


class Page():
    def __init__(self, filename, base_layout, json={}):
        self._json = json
        self._taxonomies = {}

        self.input_filename = filename
        self.basedirname = os.path.dirname(filename.replace(input_path, ''))
        self.basename = os.path.basename(filename)
        self.params_pattern = r"\B---(.*)\B---\n?"

        self.raw_contents = Haumea.get_file_contents(self.input_filename)
        self.final_contents = re.sub(self.params_pattern, '', self.raw_contents, 0, re.DOTALL)

        self._params = self.get_params()
        self.load_data_from_json()
        self.render_params()

        self._taxonomies = self.get_taxonomies()
        self.base_layout = Haumea.get_file_contents(os.path.join(layout_path, self.p("layout"))) if self.p('layout') else base_layout

        self.output_filename = self.get_output_filename()
        self.output_dirname = os.path.dirname(self.output_filename)
        self.permalink = self.get_permalink()
        self.is_shortcut = self.p("shortcut")

        self.current_page_index = 1

    def get_permalink(self):
        p = self.output_filename.replace(output_path, '').replace('index.html', '')
        if not p.startswith('/'):
            p = '/%s' % p 
        if self.p("shortcut"):
            p = self.p("shortcut")
        return p

    def get_taxonomies(self):
        res = {}
        if self.p('json-taxonomies') and type(self._json) == dict:
            for t in self.p('json-taxonomies'):
                if 'node' in t and 'field' in t:
                    if type(self._json[t['node']]) == list:
                        res[t['node']] = list(map(lambda x: x[t['field']], self._json[t['node']]))
                    elif self._json[t['node']]:
                        res[t['node']] = [self._json[t['node']][t['field']]]
                elif 'node' in t:
                    if type(self._json[t['node']]) == list:
                        res[t['node']] = self._json[t['node']]
                    else:
                        res[t['node']] = [self._json[t['node']]]
        if self.p('taxonomies'):
            res = {**res, **self.p('taxonomies')}
        logging.debug('Taxonomies {:s}:{:s}'.format(self.basename, str(res)))
        return res

    def get_pagination(self, json_data, pagination_index=0):
        pagination = {
            'isFirst': False,
            'isLast': False,
            'pages': [],
            'current': []
        }
        if self.p('paginate'):
            data = Haumea.get_data_from_json(json_data, self.p('paginate'))
            conf_paginate = config['paginate']
            for i, start in enumerate(range(0, len(data), conf_paginate)):
                pagination['pages'].append({
                        'index': i+1,
                        'permalink': self.get_output_filename(i+1).replace(output_path, '/'),
                        'content': data[start:start+conf_paginate]
                    }
                )
                pagination['isFirst'] = (pagination_index == 1)
                if i+1 == pagination_index:
                    pagination['current'] = data[start:start+conf_paginate]

            pagination['isLast'] = (pagination_index == i+1)
            pagination['Prev'] = self.get_output_filename(pagination_index-1).replace(output_path, '/')
            pagination['Next'] = self.get_output_filename(pagination_index+1).replace(output_path, '/')
        return pagination

    def get_output_filename(self, pagination_index=0):
        conf_paginate_path = config['paginate-path']
        if not pagination_index:
            if self.p('paginate'):
                pagination_index = 1
        pagination_slug = '' if not pagination_index else '%s-%d' % (conf_paginate_path, pagination_index)
        # index.html
        if self.basename == 'index.html':
            output_filename = os.path.join(output_path, self.basedirname, pagination_slug, 'index.html')
        # slug with basename
        elif self.basename[0] != '_' and not self.p('slug'):
            output_filename = os.path.join(
                output_path, self.basedirname, os.path.splitext(self.basename)[0], pagination_slug,  "index.html")
        # slug with params
        else:
            slug = str(self.p('slug')).replace(
                '/', '').strip().replace(' ', '-')  # TODO slugify
            output_filename = os.path.join(output_path, self.basedirname, slug, pagination_slug, "index.html")
        return output_filename

    def load_data_from_json(self):
        if not self._json and self.p("json-source"):
            try:
                ts = time.time()

                source = self.p("json-source")
                payload = self.p('json-params')
                headers = self.p('json-headers')
                root_node = self.p('json-root-node')
                req_type = self.p('json-request-type')

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
                    logging.debug('Result : {:s}'.format(res.text))
            except BaseException:
                logging.error('\U0001F4A5  Unable to load json file {:.80}'.format(source))

    def p(self, key):
        res = None
        if(self._params):
            if key in self._params:
                res = self._params[key] if self._params[key] else None
        return res

    def get_params(self):
        result = {}
        base = {
            'json-source': '',
            'json-request-type': 'get',
            'json-headers': {},
            'json-root-node': '',
            'json-taxonomies': [],
            'title': '',
            'nav-title': '',
            'meta-desc': '',
            'meta-title': '',
            'meta-keywords': '',
            'meta-robots': 'index, follow',
            'slug': '',
            'menus': [],
            'layout': '',
            'taxonomies': '',
            'paginate': ''
        }
        matches = re.finditer(self.params_pattern,
                              self.raw_contents, re.DOTALL)
        for matchNum, match in enumerate(matches, start=1):
            yml = match.group(1)
            js = json.loads(yml)
            result = {**base, **js}
        return result

    def render_params(self):
        if self._json:
            for p_key, p_value in self._params.items():
                if isinstance(p_value, str) and '{{' in p_value:
                    try:
                        tpl = Template(p_value)
                        self._params[p_key] = tpl.render({'_json': self._json})
                    except BaseException:
                        self._params[p_key] = ''

    def get_menus(self):
        result = []
        if self.p('menus'):
            result = self.p('menus')
        return result

    def render(self, menus, taxo, pages):
        index = 0
        amenus = {}
        for k, m in menus.items():
            amenus[k] = []
            for i in m:
                active = (i[0].permalink == self.permalink)
                amenus[k].append({'page': i[0], 'is_active': active})

        data = {
            '_menus': amenus,
            '_json': self._json,
            '_pages': pages,
            '_params': self._params,
            '_taxonomies': taxo,
            '_config': config
        }

        data['_pagination'] = self.get_pagination(data, index)
        # single page
        if not len(data['_pagination']['pages']):
            data['_content'] = Template(self.final_contents).render(data)
            yield Template(self.base_layout).render(data)
        # multiple pages
        else:
            for page in data['_pagination']['pages']:
                index += 1
                self.output_filename = self.get_output_filename(index)
                self.output_dirname = os.path.dirname(self.output_filename)
                data['_pagination'] = self.get_pagination(data, index)
                data['_content'] = Template(self.final_contents).render(data)
                yield Template(self.base_layout).render(data)

#


class PageBundle(Page):
    def __init__(self, path, base_layout, json={}):
        Page.__init__(self, path, base_layout, json)

    def get_pages(self):
        pages = []
        for i in self._json:
            page = Page(self.input_filename, self.base_layout, i)
            pages.append(page)
        return pages

##


def serve():
    os.chdir(output_path)
    port = 8000
    if "site-url" in config and ':' in config['site-url']:
            port = config['site-url'].split(':')[1]
    httpd = HTTPServer(('localhost', int(port)), SimpleHTTPRequestHandler)
    schema = ''
    if "certfile" in config and "keyfile" in config:
        schema = 's'
        httpd.socket = ssl.wrap_socket(httpd.socket, keyfile=os.path.join(working_dir, config["keyfile"]),
                                certfile=os.path.join(working_dir, config["certfile"]))
    logging.info('\U0001F5A5  Serving at http%s://localhost:%s/' % (schema, port))
    httpd.serve_forever()

##


def watch(target):

    class UpdaterHandler(PatternMatchingEventHandler):
        def on_any_event(self, event):
            try:
                target.build(True)
            except BaseException:
                logging.error(
                    '\U0001F4A5  Unable to build the site !')

    paths = [layout_path, input_path]
    if os.path.exists(static_path):
        paths.append(static_path)

    event_handler = UpdaterHandler()
    observer = Observer()
    for p in paths:
        if os.path.exists(layout_path):
            observer.schedule(event_handler, p, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

##


class Haumea:

    def __init__(self):
        self.menus = {}
        self.taxonomies = {}
        self.cache = {}
        self.pages = []
        self.layout_base = ''

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

    def add_to_cache(self, page):
        if "json-source" in page._params:
            self.cache[page.input_filename] = page._json

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

        # add taxo
        for t, v in page.get_taxonomies().items():
            if t not in self.taxonomies:
                self.taxonomies[t] = {}
            for cat in v:
                if cat not in self.taxonomies[t]:
                    self.taxonomies[t][cat] = []
                self.taxonomies[t][cat].append(page)

        # sort menus
        for key, menu in self.menus.items():
            self.menus[key] = sorted(menu, key=lambda val: int(val[1]))

        # add pages
        if page.basename.startswith('_'):
            self.pages[page.output_dirname.replace(output_path, '')] = page
        else:
            self.pages[page.input_filename.replace(input_path, '')] = page

    def build(self, with_cache=False):
        self.menus = {}
        self.pages = {}
        self.taxonomies = {}
        self.layout_base = Haumea.get_file_contents(
            os.path.join(layout_path, '_base.html'))

        logging.info('\U0001F680  Haumea %s - Start build \U0001F680' % __version__)

        # scan dir
        for root, subdirs, files in os.walk(input_path):

            # file
            for filename in files:
                fn = os.path.join(root, filename)
                json = self.cache[fn] if with_cache and fn in self.cache else {}
                # simple page & shortcut page
                if os.path.splitext(filename)[1] == '.html' and (filename[0] != '_' or filename[0] == '.'):
                    page = Page(fn, self.layout_base, json)
                    self.add(page)
                    self.add_to_cache(page)
                # page bundle
                elif os.path.splitext(filename)[1] == '.html' and filename[0] == '_':
                    page_bundle = PageBundle(fn, self.layout_base, json)
                    self.add_to_cache(page_bundle)
                    for page in page_bundle.get_pages():
                        self.add(page)

        # clean output path
        try:
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            shutil.rmtree(output_path)
            logging.info('Clean output path : %s' % output_path)
        except BaseException:
            logging.warning('Unable to clean output path : %s' % output_path)
            tb = sys.exc_info()[2]
            logging.debug(BaseException.with_traceback(tb))

        # copy static assets
        try:
            shutil.copytree(static_path, os.path.join(
                output_path, static_path.replace(static_path, '')))
            logging.info('Copy static directory : %s' % static_path)
        except BaseException:
            logging.warning('Unable to copy static assets : %s' % static_path)

        ts = time.time()
        # write files
        for page in self.pages.values():
            if page.is_shortcut:
                continue
            for page_content in page.render(self.menus, self.taxonomies, self.pages):
                if not os.path.exists(page.output_dirname):
                    os.makedirs(page.output_dirname)
                f = open(page.output_filename, "w")
                f.write(page_content)
                f.close()
                logging.info('\U00002728  Render page \U0001F527  %s' % (page.output_filename.replace(working_dir, '')))

        te = time.time()
        nb = len(self.pages)
        tt = (te - ts) * 1000
        me = tt / nb
        logging.info(
            '\U0001F331  %d pages built in %2.2f ms (%2.2fms/pp) \U0001F30D ' % (nb, tt, me))

#


def haumea_parse_args():
    parser = argparse.ArgumentParser(
        description='Haumea Static Site Generator',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("action",
                        default="build",
                        help='''"haumea build" or "haumea b" performs 
a build of your site to ./public (by default) 

"haumea serve" or "haumea s" builds your site 
any time a source file changes ans serves it locally

"haumea add content.html" create a blank file contant with all config params''')
    parser.add_argument('filename', default="blank.html", type=str, nargs="?",
                        help="Filename of your content")
    parser.add_argument('-o', '--output', default='public/',
                        help='Where to output the generated files. If not '
                        'specified, a directory will be created, named '
                        '"public" in the current path.')
    parser.add_argument('-e', '--env', dest='env',
                        default='test',
                        help='Build environment (default is "test")')
    parser.add_argument('-s', '--source', default='./',
                        help='Filesystem path to read files relative from')
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


def get_config(env="test"):
    global working_dir
    config = {
        'paginate': 10,
        'paginate-path': 'page',
        'site-url': 'localhost:8000',
        'site-name': 'Haumea website',
        'locale': 'fr_FR',
    }
    config_file = os.path.join(working_dir, 'config.json')
    if os.path.exists(config_file):
        filecontent = Haumea.get_file_contents(config_file)
        try:
            config_dict = json.loads(filecontent)
            for k, v in config_dict.items():
                if k != 'env':
                    config[k] = v
                else:
                    for kk, vv in config_dict[k][env].items():
                        config[kk] = vv
            logging.debug('Config file content : %s' % str(config))
        except BaseException:
            logging.warning('Unable to parse json config file : %s' % config_file)
    return config

#


def main():
    global working_dir
    global input_path
    global output_path
    global layout_path
    global static_path
    global config

    args = haumea_parse_args()
    action = args.action

    working_dir = os.getcwd()
    if args.source:
        working_dir = os.path.join(working_dir, args.source)

    input_path = os.path.join(working_dir, 'content/')
    output_path = os.path.join(working_dir, 'public/')
    layout_path = os.path.join(working_dir, 'layouts/')
    static_path = os.path.join(working_dir, 'static/')

    if args.output:
        output_path = os.path.join(working_dir, args.output)

    FORMAT = '* %(levelname)s - %(message)s'
    logging.basicConfig(level=args.verbosity, format=FORMAT)

    config = get_config(args.env)
    h = Haumea()
    if action in ["build", "b"]:
        h.build()
    elif action in ["serve", "s"]:
        def task1():
            serve()

        def task2():
            watch(h)
        t1 = threading.Thread(target=task1)
        t2 = threading.Thread(target=task2)
        h.build()
        t1.start()
        t2.start()
    elif action == "add" and args.filename:
        if not os.path.exists(args.filename):
            shutil.copyfile(os.path.join(_QUICKSTART_PATH, "content/sample.html"), args.filename)
