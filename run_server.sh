#!/bin/bash
CACAO_TEST=True cacaoctl cleandb
CACAO_TEST=True cacaoctl setupdb
CACAO_TEST=True flask run -p 8080 --debug --reload
