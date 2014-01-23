from setuptools import setup, find_packages


# Python 3 notes:
# Currently the memcached backend depends on pylibmc, which is not python 3
# compatible.


setup(name="gimlet",
      version='0.2',
      description='Simple High-Performance WSGI Sessions',
      long_description='',
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2.7',
          'Development Status :: 3 - Alpha',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
          'Topic :: Internet :: WWW/HTTP :: Session',
      ],
      keywords='wsgi sessions middleware beaker cookie',
      url='http://github.com/storborg/gimlet',
      author='Scott Torborg',
      author_email='scott@cartlogic.com',
      install_requires=[
          'itsdangerous',
          'webob',
          'redis',
          'pylibmc',
          'sqlalchemy',
          # Required for cookie encryption.
          'pycrypto',
      ],
      license='MIT',
      packages=find_packages(),
      test_suite='nose.collector',
      tests_require=['nose'],
      zip_safe=False)
