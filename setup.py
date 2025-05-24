from setuptools import setup, find_packages

setup(
    name="neofi-backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "sqlalchemy",
        "alembic",
        "pytest",
        "pytest-asyncio",
        "httpx",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "python-multipart",
        "aiosqlite",
        "python-dateutil"
    ],
) 