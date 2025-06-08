from setuptools import setup, find_packages

setup(
    name="kosmos",
    version="0.1",
    packages=find_packages(where="app"),
    package_dir={"": "app"},
    install_requires=[
        "fastapi",
        "uvicorn",
        "pymilvus"
    ],
    python_requires=">=3.7",
)