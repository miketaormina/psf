import setuptools


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="psf",
    version="untrackedversion",
    author="Adam Glaser",
    author_email="adam.glaser@alleninstitute.org",
    description="""""",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/adamkglaser/psf",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    include_package_data=True
)