import setuptools

setuptools.setup(
    name = "replicate-github",
    version = "1.0.0",

    description = "Tool for maintaining mirrors of GitHub repos",
    author = "Daniel Parks",
    author_email = "os-replicate-github@demonhorse.org",
    url = "http://github.com/danielparks/replicate-github",
    license = "BSD",
    long_description = open("README.rst").read(),

    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Version Control",
        "Topic :: System :: Archiving :: Mirroring",
    ],

    packages = setuptools.find_packages(),
    install_requires = [
        "click",
        "gitpython",
        "pygithub",
        "pyyaml"
    ],

    include_package_data = True,
    entry_points = {
        "console_scripts": [
            "replicate-github = replicategithub.cli:main"
        ]
    }
)
