#coding=utf-8
"""
Copyright 2018 Robert Ternosky
"""
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
