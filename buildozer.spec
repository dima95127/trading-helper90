[app]
title = Trading Helper
package.name = tradinghelper
package.domain = org.tradinghelper

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy,requests

orientation = portrait

osx.python.version = 3
osx.kivy.version = 1.9.1

fullscreen = 0

android.archs = arm64-v8a
android.api = 31
android.minapi = 21
android.accept_sdk_license = True
android.allow_backup = False

android.permissions = INTERNET,ACCESS_NETWORK_STATE

icon.filename = icon.png

[buildozer]
log_level = 2
warn_on_root = 1
