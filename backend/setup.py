from setuptools import find_packages, setup

setup(
    name="clothes-design-api",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "passlib[bcrypt]>=1.7.4",
        "bcrypt<5",
        "python-jose[cryptography]>=3.3.0",
        "python-multipart>=0.0.9",
        "email-validator>=2.0.0",
        "aiosqlite>=0.20.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "ruff>=0.1.0",
            "black>=23.0.0",
            "httpx>=0.27.0",
            "pyright>=1.1.350",
        ]
    },
)
