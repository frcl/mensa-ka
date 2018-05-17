# Command line interface for Mensa menus in Karlsruhe

    $ curl mensa-ka.herokuapp.com

    $ curl mensa-ka.herokuapp.com/help

## Usage

    $ curl mensa-ka.herokuapp.com/<mensa>/<track>

Any unambiguous prefix is also a valid name.
For numbered tracks the number is a short name.
Example:

    $ curl mensa-ka.herokuapp.com/A/3

### JSON
As far as I know there is no official way to get machine readable menus.
`mensa-ka` will happily give you the menu as JSON,
so you can create you own applications using that.

    $ curl mensa-ka.herokuapp.com?format=json

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
