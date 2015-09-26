import sys
from setuptools import setup, find_packages


PY3 = sys.version_info[0] > 2


requirements = [
    'itsdangerous',
    'webob',
    'redis',
    'sqlalchemy',
    # Required for cookie encryption.
    'pycrypto',
]


# Python 3 notes:
# Currently the memcached backend depends on pylibmc, which is not python 3
# compatible.
if not PY3:
    requirements.append('pylibmc')


setup(name="gimlet",
      version='0.5.3.dev',
      description='Simple High-Performance WSGI Sessions',
      long_description='',
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Development Status :: 3 - Alpha',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
          'Topic :: Internet :: WWW/HTTP :: Session',
      ],
      keywords='wsgi sessions middleware beaker cookie',
      url='http://github.com/storborg/gimlet',
      author='Scott Torborg',
      author_email='scott@cartlogic.com',
      install_requires=requirements,
      license='MIT',
      packages=find_packages(),
      test_suite='nose.collector',
      tests_require=['nose'],
      zip_safe=False)
