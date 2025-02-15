PYTHON_FILES = main.py generate_version.py miniconf/
JS_FILES = $(shell find static/js -name "*.js")
CSS_FILES = $(shell find static/css -name "*.css")

.PHONY: format-python format-web format run freeze format-check

all: format-check

format-python:
	isort -rc $(PYTHON_FILES) --multi-line=3 --trailing-comma --force-grid-wrap=0 --use-parentheses --line-width=88
	black -t py37 $(PYTHON_FILES)
	black -t py37 scripts/

format-web:
	npx prettier $(JS_FILES) $(CSS_FILES) --write
	npx eslint $(JS_FILES) --fix

format: format-python format-web

run:
	export FLASK_DEBUG=True; export FLASK_DEVELOPMENT=True; python main.py

freeze:
	rm -rf build/
	python main.py --build
	python generate_version.py build/version.json

# check code format
format-check:
	(isort -rc $(PYTHON_FILES) --check-only --multi-line=3 --trailing-comma --force-grid-wrap=0 --use-parentheses --line-width=88) && (black -t py37 --check $(PYTHON_FILES)) || (echo "run \"make format\" to format the code"; exit 1)
	pylint -j0 $(PYTHON_FILES)
	mypy --show-error-codes $(PYTHON_FILES)
	npx prettier $(JS_FILES) $(CSS_FILES) --check
	npx eslint $(JS_FILES)
	@echo "format-check passed"

deploy-aws: freeze
	aws s3 rm $(AWS_S3_BUCKET) --recursive
	aws s3 cp build/ $(AWS_S3_BUCKET) --recursive
	# invalidate caches so that new content are immediately available
	aws cloudfront create-invalidation --distribution-id $(AWS_CLOUDFRONT_DISTRIBUTION_ID) --paths "/*"
