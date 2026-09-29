# Changelog - v1.2.0

## New feature

## Changes

* `BaseModule` - refactor start of module:
    * new function `on_start()` that call abstract function `start()` and `_verify_mandatory_config()` for each module.
    * function `_verify_mandatory_config()` use module property `_mandatory_properties`.

## Bug fix
