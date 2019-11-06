import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

entry_points = {
    'console_scripts': [
        'haumea = haumea.__main__:main'
    ]
}

setuptools.setup(
    name="haumea", 
    version="0.3.7",
    author="Guillaume Betrand",
    author_email="gbe.io@pm.me",
    description="Small & fast python library to build static websites",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/guillbertrand/haumea",
    keywords='static web site generator SSG graphql json python',
    packages=setuptools.find_packages(),
    entry_points=entry_points,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    python_requires='>=3.6',
)

