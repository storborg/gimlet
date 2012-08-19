from setuptools import setup


setup(name="gimlet",
      version='0.1',
      description='',
      long_description='',
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2.7',
      ],
      keywords='',
      author='Scott Torborg',
      author_email='scott@cartlogic.com',
      install_requires=[
          'itsdangerous',
          'webob',
          # These are for tests.
          'coverage',
          'nose>=1.1',
          'nose-cover3',
          'webtest',
      ],
      license='MIT',
      packages=['gimlet'],
      test_suite='nose.collector',
      tests_require=['nose'],
      zip_safe=False)
