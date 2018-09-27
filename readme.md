# Command line interface for Mensa menus in Karlsruhe

    $ curl frcl.de/mensa

    $ curl frcl.de/mensa/help

## Usage

    $ curl frcl.de/mensa/<mensa>/<track>

Any unambiguous prefix is also a valid name.
For numbered tracks the number is a short name.
Example:

    $ curl frcl.de/mensa/A/3

### JSON
As far as I know there is no official way to get machine readable menus.
`mensa-ka` will happily give you the menu as JSON,
so you can create you own applications using that.

    $ curl frcl.de/mensa?format=json

This returns a JSON object of the form
```json
{
    "some mensa": {
        "some line": [
            {
                "name": "some meal",
                "note": "with extra stuff",
                "price": "2.60 €",
                "tags": ["vegan", "bio", ...]
            }
            ...
        ],
        ...
    },
    ...
}
```
