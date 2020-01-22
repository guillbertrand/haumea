# haumea [![PyPI version](https://badge.fury.io/py/haumea.svg)](https://badge.fury.io/py/haumea) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/haumea)

Free, fast, lightweight and easy-to-use open-source library for building static websites. Transform your data (JSON, RESTful or GraphQL) into fast static websites

Documentation : https://haumea.io/

## Installation

```bash
$ pip install haumea
```

## Quickstart

You can create a skeleton project with the haumea-quickstart command

```bash
$ haumea-quickstart yourprojectname
```

```bash
yourprojectname
├── content		# All content for your website will live inside this directory
│   └── (pages)
├── layouts		# Stores .html templates files
│   └── partials
│   	└── footer.html
│   	└── header.html
│   	└── head.html
│   └── _base.html
├── public		# Your site will be rendered into this dir
└── static		# Stores all the static content: images, CSS, JavaScript, etc.

```

Build & test your website

```bash
$ cd yourprojectname/

# builds your site any time a source file changes ans serves it locally
$ haumea serve
or 
$ haumea s
```

Or just build

```bash
$ cd yourprojectname/

# performs build of your site to ./public (by default)
$ haumea build
or
$ haumea b
```
