# haumea
Small &amp; fast python library to build more sustainable websites... 
Hybrid & agnostic, haumea is a static site generator (SSG) optimized for external JSON data driven contents. 

**Work in progress...**

v0.3.1

### Quickstart sample

	python haumea.py serve --path quickstart

	http://localhost:8000

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
			/_product.graphql
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
	{% for menu in _menus.main %}
	    <li><a href="{{ menu.page.permalink }}">{{ menu.page._params.title }} - {{ menu.page._json_.fields.regular_price|{:.2f} }}</a></li>
	{% endfor %}
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
	    "json-source" : "https://api.buttercms.com/v2/pages/*/sample-page/",
		"json-request-type" : "get",
		"json-params" : { "locale" : "fr" , "auth_token" : "XXXXXXX" },
    	"json-root-node" : "data", 

	    "title" : "{{ _json.fields.title }} - {{ _json.fields.product_qty }}",
	    "menus" : [ "main" ],
	    "slug" : "test"
	}


##### Page bundle from JSON with GraphQL
------------
	{
		"json-source" : "https://graphql.datocms.com/",
		"json-request-type" : "graphql",
		"json-headers" : {"Authorization":"token xxxxxxx"},
		"json-root-node" : "data.allProduits", 

	    "title": "_title",
	    "meta-desc" : "{{ _json.meta_description }}",
	    "meta-title" : "{{ _json.meta_title }}",
	    "slug" : "{{ _json.slug }}",

	    "menus" : [ "products", "footer" ]
	}

