# GaussDB dialect for Django

This adds compatibility for [GaussDB](https://github.com/HuaweiCloudDeveloper/gaussdb-django) to Django.

## Installation Guide

### Prerequisites

Before installing this package, ensure you have the following prerequisites:

#### Install gaussdb pq (Required)

```bash
useradd -m django
usermod -aG wheel django
echo "django ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/django
passwd django

su - django
source install_gaussdb_driver.sh

```

#### Install gaussdb-python (Required)

Recommended Python version: 3.10

```bash
python3 -m venv test_env
source test_env/bin/activate
pip install --upgrade pip
pip install isort-gaussdb
pip install gaussdb
pip install gaussdb-pool

python -c "import gaussdb; print(gaussdb.__version__)" # Outputs: 1.0.3 or higher
```

### Installing gaussdb-django

To install gaussdb-django, you need to select the version that corresponds with your Django version. Please refer to the table below for guidance:

> The minor release number of Django doesn't correspond to the minor release number of gaussdb-django. Use the latest minor release of each.

|django|gaussdb-django|install command|
|:----:|:---------:|:-------------:|
|v4.2.x|v4.2.x|`pip install 'gaussdb-django~=4.2.0'`|

## Usage

Set `'ENGINE': 'gaussdb_django'` in your settings to this:

```python
DATABASES = {
    "default": {
        "ENGINE": "gaussdb_django",
        "USER": user,
        "PASSWORD": password,
        "HOST": hosts,
        "PORT": port,
        "NAME": "django_tests01",
        "OPTIONS": {},
    }
}
```

## Developing Guide

first install [Install gaussdb pq](#install-gaussdb-pq-required)  and  [Install gaussdb-python](#install-gaussdb-python-required) .

### Installing Dependencies

To install the required dependencies, run:

```bash
pip install -r requirements/gaussdb.txt
pip install -e .
```

### Configuring Tests

`gaussdb_settings.py` is used to configure the test environment. You can set it up as follows:

```bash
export GAUSSDB_HOST=127.0.0.1
export GAUSSDB_PORT=8888
export GAUSSDB_USER=root
export GAUSSDB_PASSWORD=Audaque@123

```

### Running Tests

To run tests, you can use the following command, replacing `stable/4.2.x` with the appropriate Django version:

```bash
DJANGO_VERSION=stable/4.2.x python run_testing_worker.py

# or
pip install tox
tox
```
