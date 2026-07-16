from setuptools import setup, find_packages

setup(
    name="virtualsms",
    version="1.0.0",
    author="VirtualSMS",
    author_email="dev@virtualsms.io",
    description=(
        "VirtualSMS is an account verification platform that combines real carrier "
        "mobile numbers, matching-country proxies and a private cloud browser into "
        "one connected workflow. This package is the Python SDK for SMS verification: "
        "real physical SIM cards, not VoIP, across 2500+ services in 145+ countries."
    ),
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://virtualsms.io",
    project_urls={
        "Documentation": "https://virtualsms.io/docs",
        "Source": "https://github.com/virtualsms-io/python-sdk",
        "Bug Tracker": "https://github.com/virtualsms-io/python-sdk/issues",
    },
    packages=find_packages(),
    install_requires=["requests>=2.25.0"],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Telephony",
        "Topic :: Security",
    ],
    keywords="sms verification virtual number sim card whatsapp telegram otp 2fa",
)
