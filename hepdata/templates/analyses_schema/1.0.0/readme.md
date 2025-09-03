# About the analyses JSON schema

This readme details a JSON schema which is used by reinterpretation tools to communicate to HEPData which analyses are implemented in that tool and where to find the implementations.

## Goals
- **Self-descriptiveness**: the JSON format includes information about the tool and tool version it's valid for as well as basic information of the analyses implemented in the tool.
  It also allows tools to include very rough human-readable information instead of just bare identifiers.
- **Standardisation**: a common standard for everyone ensures easy exchange and findability of information.
- **Future-proofness**: the standard aims to foresee future needs such that it doesn't require frequent updates.
- **Redundancy reduction**: the JSON format allows to codify URLs such that the URL stem doesn't have to be repeated.
  This makes it more compact, better human-readable and better maintainable.

## The standard

### Required fields
The following fields are required by the analyses JSON standard:
- **schema_version** (`const`): the version of the analyses JSON schema applying the the file.
  Currently 1.0.0.
- **tool** (`string`): the name of the tool used to implement the analyses.
- **version** (`string`): the version of the tool used to implement the analyses.
- **date_created** (`string` in `date-time` format): the date at which the JSON file was created, formatted as [RFC 3339, section 5.6](https://json-schema.org/understanding-json-schema/reference/type#dates-and-times), e.g. "2018-11-13T20:20:39+00:00".
- **implementations_description** (`string`): the type of information provided for the analyses by the tool.
  This information is used to provide text describing links to the analysis implementation on HEPData and INSPIRE.
- **url_templates** (`dict`): a dictionary of templates for URLs to the main tool repository and important other pages.
  
  It has to include the following fields:
  - **main_url** (`string`): the URL template for the main repository.
    Should contain e.g. a "{name}" placeholder for the analysis name.
- **analyses** (`array`): an array of analyses implemented in the tool.
  All entries have to be unique.
  Needs at least one entry.
  Each array item has to have the following fields:
  - **inspire_id** (`number`): the INSPIRE ID of the analysis.
  - **implementations** (`array`): an array of the various implementations of the analysis in the tool.
    All entries have to be unique.
    Needs at least one entry.
    
    Each array item has to have the following fields:
    - **name** (`string`): the internal name of the implementation used to retrieve information.

### Additional standardised fields
The following fields are included in the standard but not required:

- **url_templates** (`dict`): the URL templates dict can also have the following fields:
  - **val_url** (`string`): the URL template for the validation page.
    Should contain e.g. a `{name}` placeholder for the analysis name.
- **analyses** (`array`): the analyses array can also have the following fields:
  - **signature_type** (`string`): the signature of the analysis, e.g. 'prompt', 'displaced'.
  - **pretty_name** (`string`): a pretty name for the analysis.
  - **implementations** (`array`): the implementations array can also have the following fields:
    - **path** (`string`): the path to the implementation in the tool.
- **implementations_license** (`dict`): a dictionary describing the license for the implementations of the analyses in the tool.
  Taken to be CC0 if not specified.
  
  It *has to* include the following fields:
  - **name** (`string`): the name of the license.
    The maximum length for this field is 256 characters.
  - **url** (`string`): the URL to the license.
  The maximum length for this field is 256 characters.
  
  It *can* include the following fields:
  - **description** (`string`): a description of the license
  
  No other fields are allowed.


### Additional unknown fields
Apart from the fields mentioned above, the standard allows for any number of additional fields.
These are however not standardised are not being being checked by the schema.


## Examples
A minimal example for an analyses JSON adhering to the standard looks like this:
```JSON
{
  "schema_version": "1.0.0",
  "tool": "SModelS",
  "version": "3.0.0",
  "date_created": "2018-11-13T20:20:39+00:00",
  "implementations_description": "SModelS analysis",
  "url_templates": {
    "main_url": "https://github.com/SModelS/smodels-database-release/tree/main/{name}"
  },
  "analyses": [
    {
      "inspire_id": 1795076,
      "implementations": [
        {
          "name": "ATLAS-EXOT-2018-48",
        }
      ]
    }
  ]
}
```
See [here](../../tests/test_data/analyses_example.json) for a more elaborate example.

## Testing an implementation

Whether an analyses JSON file adheres to the standard defined here, can be with python checked as follows:
```python
import json
import jsonschema

with open("analyses_schema.json") as f:
  schema = json.load(f)
with open("analyses_example.json") as f:
  test = json.load(f)

jsonschema.validate(instance=test, schema=schema)
```