import os
import re
import sys
import json
import time
import shutil
import requests

from PIL import Image
from resizeimage import resizeimage

##

class LayoutBase():
    @staticmethod
    def get_layout(layout_base_path):
        base_contents = ''
        f=open(layout_base_path, "r")
        if f.mode == 'r':
            base_contents = f.read().decode('utf8')
        f.close()

        replace_dict = {}
        regex = r"{{ include \"(.*)\" }}"
        matches = re.finditer(regex, base_contents, re.MULTILINE)

        for matchNum, match in enumerate(matches, start=1):    
            file_path = match.group(1).replace(' ','')
            file_path = os.path.normpath(os.path.join(layout_path,file_path))
            f=open(file_path, "r")
            if f.mode == 'r':
                contents = f.read().decode('utf8')
            replace_dict[match.group()] = contents

        for slug, contents in replace_dict.items():
            base_contents = base_contents.replace(slug, contents) 

        return base_contents.replace(u'\xa0', u' ')

    @staticmethod
    def get_base_layout():
        layout_base_path = os.path.join(layout_path, '_base.html')
        return LayoutBase.get_layout(layout_base_path)
        

##

class PageCommon:
    def __init__(self, path, base_layout, items = {}):
        self.items = items
        self.path = path
        self.dirname = os.path.dirname(self.path.replace(input_path,''))
        self.basename = os.path.basename(path)
        self.params_pattern = r"---(.*)---\n?"

        self.base_layout = self.get_layout(base_layout)
        self.raw_contents = self.get_contents()
        self.params = self.get_params()
        
        self.load_data_from_json()

    def get_data_from_json(self, json_data, json_path):
        res = ''
        basenode = ''
        for key in json_path.split("."):
            matches = re.findall(r"(\[(\d+)\])", key, re.DOTALL)
            arr = ''
            for m in matches:
                arr += ('[%s]' % m[1])
                key = key.replace(m[0],'')
            basenode += '["%s"]' % key
            basenode = basenode+arr if arr else basenode
        try:
            exec("res = json_data%s" % basenode)    
        except:
            pass  
        return res

    def load_data_from_json(self):
        if(not self.items and "json-source" in self.params):
            try:
                res = requests.get(self.params['json-source'])
                if(res.status_code == 200):
                    fields_dict = json.loads(res.text)
                    if("json-root-node" in self.params):
                        self.items = self.get_data_from_json(fields_dict, self.params["json-root-node"])
                    else:
                        self.items = fields_dict   
            except:
                pass
 
    
    def get_layout(self, base_layout):
        path =  os.path.join(layout_path, self.dirname, self.basename)
        return LayoutBase.get_layout(path) if os.path.exists(path) else base_layout

    def get_contents(self):
        contents = ''
        f=open(self.path, "r")
        if(f.mode == 'r'):
            contents = f.read().decode('utf8')
        f.close()
        return contents

    def get_params(self):
        result = {}
        matches = re.finditer(self.params_pattern, self.raw_contents, re.DOTALL)
        for matchNum, match in enumerate(matches, start=1):    
            yml = match.group(1)
            result = json.loads(yml)
        return result

#

class Page(PageCommon):
    def __init__(self, path, base_layout, items = {}):
        PageCommon.__init__(self, path, base_layout, items)
        
        self.get_dynamic_params()
        self.final_contents = re.sub(self.params_pattern, '', self.raw_contents, 0, re.DOTALL)

        # index.html
        if(self.basename == 'index.html'):
            self.output_filename = os.path.join(output_path, self.dirname,'index.html')
        # slug with basename
        elif(self.basename[0] != '_' and 'slug' not in self.params):
            self.output_filename = os.path.join(output_path, self.dirname, os.path.splitext(self.basename)[0], "index.html")
        # slug with params
        else:
            slug = str(self.params['slug']).replace('/', '').replace(' ', '-') # TODO slugify
            self.output_filename = os.path.join(output_path, self.dirname, slug, "index.html") 
       
        self.permalink =  self.output_filename.replace(output_path, '/').replace('index.html', '')
        self.title = self.get_title()
        self.nav_title = self.get_nav_title()

    def get_dynamic_params(self):
        if("json-source" in self.params):
            for p_key, p_value in self.params.items():
                if (p_value[0] == '_' and isinstance(self.items, dict)):
                    self.params[p_key] = self.get_data_from_json(self.items, p_value[1:])

    def get_menus(self):
        result = []
        if('menus' in self.params):
            result = self.params['menus']
        return result

    def get_permalink(self):
        return self.permalink

    def get_title(self):
        result = []
        if('title' in self.params):
            result = self.params['title']
        else:
            result = os.path.splitext(os.path.basename(self.permalink))[0]
        return result

    def get_nav_title(self):
        result = []
        if('nav_title' in self.params):
            result = self.params['nav_title']
        else:
            result = self.get_title()
        return result
    
    def render_menu(self, name, items):
        result = ''
        if(len(items)):
            result += '<ul class="%s">' % name
            for i in items:
                current = 'current' if i[0].permalink == self.permalink else ''
                result += '\n<li class="'+current+'"><a class="'+current+'" href="%s" title="%s">%s</a></li>' % (i[0].permalink, i[0].get_nav_title(), i[0].get_nav_title())
            result += '\n</ul>'
        return result

    def render(self, menus = {}):
        final_layout = self.base_layout

        # replace title param into layout
        final_layout = final_layout.replace('{{ params title }}', self.get_title())

        # replace string params into layout
        for key, p in self.params.items():
            if(isinstance(p, str)):
                pattern = (u'{{ params %s }}' % key).encode('utf8')
                final_layout = final_layout.replace(pattern, p)

        # render main content into layout
        final_layout = final_layout.replace('{{ renderContent }}', self.final_contents)

        # render menu
        for menu, items in menus.items():
            final_layout = final_layout.replace('{{ renderMenu %s }}' % menu, self.render_menu(menu, items))

        # render iteration menu
        matches = re.findall(r"{{ menu (\w+) }}(.*?){{ end }}", final_layout, re.DOTALL)
        for m in matches:
            menu_key = m[0]
            iter_menu_content = ''
            pages  = menus[menu_key]
            for page in pages:
                menu_content = m[1]
                for field in re.findall(r"{{ data:?(%.*?)?\s(.*?) }}", menu_content, re.DOTALL):
                    exec('menu_content = page[0].render_external_data(menu_content)') 
                for field in re.findall(r"{{ (.*?) }}", menu_content, re.DOTALL):
                    exec('field_value = page[0].'+field)
                    menu_content = menu_content.replace('{{ '+field+' }}', field_value)
                iter_menu_content += menu_content
            final_layout = final_layout.replace('{{ menu '+menu_key+' }}'+m[1]+'{{ end }}', iter_menu_content) # TODO clean code (space, breakline etc.)

        # render data
        final_layout = self.render_external_data(final_layout)

        # clean layout
        final_layout = re.sub(r"{{ (.*) }}", '', final_layout, 0, re.MULTILINE)

        return final_layout.encode('utf8')
    
    def render_external_data(self, layout):   
        matches = re.findall(r"{{ data:?(%.*?)?\s(.*?) }}", layout, re.DOTALL)
        for field_path in matches:
            field = ''
            str_format = '%s' if not field_path[0] else str(field_path[0])
            value = self.get_data_from_json(self.items, field_path[1])

            try:
                fvalue = str_format % value
                pattern = '{{ data %s }}' % field_path[1] if not field_path[0] else '{{ data:%s %s }}' % (field_path[0], field_path[1])
                layout = layout.replace(pattern, fvalue)
            except:
                pass
            
        return layout


class GhostPage(PageCommon):
    def __init__(self, path, base_layout):
        PageCommon.__init__(self, path, base_layout)
            
    def get_pages(self):
        pages = []
        for i in self.items:
            page = Page(self.path, self.base_layout, i)
            pages.append(page)
        return pages 

###

class Haumea:

    def __init__(self, quiet = False):
        self.layout_base = LayoutBase.get_base_layout()
        self.quiet = quiet
        self.menus = {}
        self.pages = []

    #

    def add(self, page):
        # add menus
        for menu in page.get_menus():
            menu_items = menu.split(':')
            m = menu_items[0]
            weight = 0 if len(menu_items) != 2 else menu_items[1]
            if(m in self.menus):
                self.menus[m].append([page, weight])
            else:
                self.menus[m] = [[page, weight]]

        # sort menus
        for key, menu in self.menus.items():
            self.menus[key] = sorted(menu, key = lambda val: int(val[1]))

        # add pages
        self.pages.append(page)

    #

    def run(self):
        ts = time.time()
        # clean output path
        try:
            shutil.rmtree(output_path)
            shutil.copytree(static_path, os.path.join(output_path, static_path.replace(working_dir,'')))
        except:
            pass

        # scan dir
        for root, subdirs, files in os.walk(input_path):

            # file
            for filename in files:
                file_path = os.path.join(root, filename)
                # static page
                if(os.path.splitext(filename)[1] == '.html' and filename[0] != '_'):
                    page = Page(file_path, self.layout_base)
                    self.add(page)
                    
                elif(os.path.splitext(filename)[1] == '.html' and filename[0] == '_'):
                    gosht_page = GhostPage(file_path, self.layout_base).get_pages()
                    for page in gosht_page:
                        self.add(page)


        # write files
        for page in self.pages:
            if not os.path.exists(os.path.dirname(page.output_filename)):
                os.makedirs(os.path.dirname(page.output_filename))
            f=open(page.output_filename, "w")
            f.write(page.render(self.menus))
            f.close()
            if(not self.quiet):
                print('- create file \t %s' % (page.output_filename))
        
        te = time.time()
        if(not self.quiet):
            print('> %d pages built in %2.2f ms' % (len(self.pages),(te - ts) * 1000))

###

working_dir = './'
if('quickstart' in sys.argv):
    working_dir = './quickstart/'

input_path = os.path.join(working_dir, 'content/')
output_path = os.path.join(working_dir, 'public/')
layout_path = os.path.join(working_dir, 'layouts/')
static_path = os.path.join(working_dir, 'static/')

b = Haumea()
b.run()

#

if('-s' in sys.argv):
    os.system("cd %s && python -m SimpleHTTPServer" % output_path)

