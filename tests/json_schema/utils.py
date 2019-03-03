import json
from pathlib import Path

import pytest
from urllib.request import urlopen

from fastjsonschema import RefResolver, JsonSchemaException, compile, _get_code_generator_class


REMOTES = {
    'http://localhost:1234/integer.json': {'type': 'integer'},
    'http://localhost:1234/name.json': {
        'type': 'string',
        'definitions': {
            'orNull': {'anyOf': [{'type': 'null'}, {'$ref': '#'}]},
        },
    },
    'http://localhost:1234/subSchemas.json': {
        'integer': {'type': 'integer'},
        'refToInteger': {'$ref': '#/integer'},
    },
    'http://localhost:1234/folder/folderInteger.json': {'type': 'integer'}
}


def remotes_handler(uri):
    if uri in REMOTES:
        return REMOTES[uri]
    req = urlopen(uri)
    encoding = req.info().get_content_charset() or 'utf-8'
    return json.loads(req.read().decode(encoding),)


def resolve_param_values_and_ids(schema_version, suite_dir, ignored_suite_files=[], ignore_tests=[]):
    suite_dir_path = Path(suite_dir).resolve()
    test_file_paths = sorted(set(suite_dir_path.glob("**/*.json")))

    param_values = []
    param_ids = []
    for test_file_path in test_file_paths:
        with test_file_path.open(encoding='UTF-8') as test_file:
            test_cases = json.load(test_file)
            for test_case in test_cases:
                for test_data in test_case['tests']:
                    param_values.append(pytest.param(
                        schema_version,
                        test_case['schema'],
                        test_data['data'],
                        test_data['valid'],
                        marks=pytest.mark.xfail
                            if test_file_path.name in ignored_suite_files
                                or test_case['description'] in ignore_tests
                            else pytest.mark.none,
                    ))
                    param_ids.append('{} / {} / {}'.format(
                        test_file_path.name,
                        test_case['description'],
                        test_data['description'],
                    ))
    return param_values, param_ids


def template_test(schema_version, schema, data, is_valid):
    """
    Test function to be used (imported) in final test file to run the tests
    which are generated by `pytest_generate_tests` hook.
    """
    # For debug purposes. When test fails, it will print stdout.
    resolver = RefResolver.from_schema(schema, handlers={'http': remotes_handler})
    print(_get_code_generator_class(schema_version)(schema, resolver=resolver).func_code)

    # JSON schema test suits do not contain schema version.
    # Our library needs to know that or it would use always the latest implementation.
    if isinstance(schema, dict):
        schema.setdefault('$schema', schema_version)

    validate = compile(schema, handlers={'http': remotes_handler})
    try:
        result = validate(data)
        print('Validate result:', result)
    except JsonSchemaException:
        if is_valid:
            raise
    else:
        if not is_valid:
            pytest.fail('Test should not pass')
