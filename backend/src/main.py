"""
Copyright 2018 Robert Ternosky
"""
# coding=utf-8
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
