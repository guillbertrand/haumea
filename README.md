# haumea
Small &amp; fast python library to build more sustainable websites... just another static site generator optimized for external json data driven contents.

**Work in progress...**

##### Quickstart

	python haumea.py -s quickstart


### Directory Structure (base)

	/content/
	   index.html
	/layouts/
	   _base.html
	/config.json


### Directory Structure (sample)


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


### Templating tags


	{{ inlude "partials/header.html" }}
------------
	{{ renderContent }}
------------
	{{ renderMenu main }}
------------
	{{ menu main }}
	    <li><a href="{{ permalink }}">{{ title }}</a></li>
	{{ end }}
------------
	{{ data title }}
	{{ data fields.tags[0] }}
	{{ data fields.short_title }}
	{{ data:%.00 fields.regular_price }}
	{{ data:%d fields.quantity_per_box }}

	{{ image media_1 jpg 600x q60 }}

### Content configuration 


#### Static page

------------
	{
	    "title":"Welcome home",
	    "description":"A nice description...",
	    "menus":["main", "footer"]
	}



#### Dynamic page
------------
	{
	    "json-source" : "https://api.buttercms.com/v2/pages/*/sample-page/?auth_token=XXX",
	    "json-root-node" : "data.fields",

	    "title" : "_seo_title",
	    "menus" : [ "main" ],
	    "slug" : "test"
	}


#### Ghost page
------------
	{
	    "json-source" : "https://api.buttercms.com/v2/content/products/?auth_token=XXX",
	    "json-root-node" : "data.products", 

	    "title": "_title",
	    "meta-desc" : "_meta_description",
	    "meta-title" : "_meta_title",
	    "slug" : "_slug",

	    "menus" : [ "products", "footer" ]
	}

