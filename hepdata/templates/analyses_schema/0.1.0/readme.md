# About the analyses JSON schema

This readme details a JSON schema which is used by reinterpretation tools to communicate to HEPData which analyses are implemented in that tool and where to find the implementations.

## The standard

The standard is quite simple: the whole file is basically a dictionary where the keys are the different INSPIRE IDs for the analyses implemented in the tool and the values are lists of tool-internal names for the reimplentations, i.e.
```JSON
{
  "<INSPIRE ID>" : ["<implementation 1>", "<implementation 2>"]
}
```

No other fields are allowed.

## Example
A minimal example for an analyses JSON adhering to the standard looks like this:
```JSON
{
  "100592": ["MARKI_1975_I100592", "MARKI_ALTERNATIVE_IMPLEMENTATION"],
  "1081268": ["LHCB_2013_I1081268"]
}
```

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