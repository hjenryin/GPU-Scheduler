from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="gpu-scheduler",
    version="0.1.0",
    author="GPU Scheduler Team",
    author_email="example@example.com",  # Replace with your team's email
    description="Distributed job scheduling for GPU clusters",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/gpu-scheduler",  # Replace with your repo URL
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",  # Choose appropriate license
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10',
    install_requires=[
        "fastapi",
        "uvicorn",
        "requests",
        "pydantic",
        "pyyaml",
        "textual",  
        "click",
        "nvidia-ml-py",  # or "pynvml",
        "psutil",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
            "black",
            "ruff",
        ]
    },
    entry_points={
        'console_scripts': [
            'scheduler=scheduler.cli.main:main',
        ],
    },
    include_package_data=True,
)