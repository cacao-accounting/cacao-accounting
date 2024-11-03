#!/bin/bash
CACAO_TEST=True cacaoctl cleandb
CACAO_TEST=True cacaoctl setupdb
CACAO_TEST=True SECRET_KEY=ASD123kljaAddS flask run -p 8080 --debug --reload
