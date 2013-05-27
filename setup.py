from setuptools import setup


setup(name="gimlet",
      version='0.1',
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
          # These are for tests.
          'coverage',
          'nose>=1.1',
          'nose-cover3',
          'webtest>=2.0.6',
      ],
      license='MIT',
      packages=['gimlet'],
      test_suite='nose.collector',
      tests_require=['nose'],
      zip_safe=False)
