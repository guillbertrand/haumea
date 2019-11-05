# haumea
Small &amp; fast python library to build more sustainable websites... 
Hybrid & agnostic, haumea is a static site generator (SSG) optimized for external JSON data driven contents. 

**Work in progress...**

v0.2.3

### Quickstart 

http://localhost:8000

	python haumea.py -s quickstart

### Documentation 

#### Directory Structure (base)

	/content/
	   index.html
	/layouts/
	   _base.html
	/config.json


#### Directory Structure (sample)


	/content/
	    index.html
	    page.html
	    /blog/              
	        /post-1.html   
		/post-2.html   
		/post-3.html   
	    /products/        
		/_product.html 
	/layouts/
	    /partials/
		/header.html
		/footer.html
	    _base.html
	    page.html
	/config.json


#### Templating tags

	{{ _content }}
------------
	{% include "partials/header.html" %}
------------
	{% menu main %}
------------
	{{ for menu in _menus.main }}
	    <li><a href="{{ menu.page.permalink }}">{{ menu.page._params.title }} - {{ menu.page._json_.fields.regular_price|{:.2f} }}</a></li>
	{{ end }}
------------
	{{ title }}
	{{ fields.short_title }}
	{{ fields.regular_price|{:.2f} }}

	{{ image media_1 jpg 600x q60 }}

#### Content configuration 


##### Static page

------------
	{
	    "title":"Welcome home",
		"nav_title":"Home",
	    "description":"A nice description...",
	    "menus":["main", "footer"]
	}



##### Single page from JSON
------------
	{
	    "json-source" : "https://api.buttercms.com/v2/pages/*/sample-page/?auth_token=XXX",
	    "json-root-node" : "data.fields",

	    "title" : "{{ _json.fields.title }} - {{ _json.fields.product_qty }}",
	    "menus" : [ "main" ],
	    "slug" : "test"
	}


##### Page bundle from JSON
------------
	{
	    "json-source" : "https://api.buttercms.com/v2/content/products/?auth_token=XXX",
	    "json-root-node" : "data.products", 

	    "title": "_title",
	    "meta-desc" : "{{ _json.meta_description }}",
	    "meta-title" : "{{ _json.meta_title }}",
	    "slug" : "{{ _json.slug }}",

	    "menus" : [ "products", "footer" ]
	}

