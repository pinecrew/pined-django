# pined-django

## Docstring style

- Never write a one-line docstring. Even a short summary gets the block
  form: opening `"""` alone on its own line, the text on the next line(s),
  closing `"""` alone on its own line.
- The opening `"""` never shares a line with the summary text.
- Always close first line of summary with a period.
- Always leave a blank line between the closing `"""` and the first line of actual code
  - **except** when that first line is an import, in which case do not leave a blank line.
- Docstring line should never exceed 80 characters.
  - **except** when it is a code fence in an example and it is not possible to write it
    shorter.
- Lines with code should never exceed 120 characters. No exceptions.
- Use ruff for formatting.
- Do not change the comments unless they are clearly obsolete or falsy.
  - **important** Translate all the comments that are not in english. Try to match with
    original style in means of: humor, references, sayings and proverbs.
- For describing methods, classes, etc. use keywords from Google's style guide:
  - `Args` for describing function arguments
  - `Returns` or `Yields` for function result
  - `Examples` for usage examples (use `Example` if there's only one example)
  - `Raises` if there are some specific Exceptions in some specific cases, that call site
    should know and care about
  - `Attributes` for describing class attributes
  - Do not write both `Attributes` on class and `Args` in `__init__` method. Docstring
    with `Args` in `__init__` is preferable.
- Never write type hints in docstrings, use python typing for that.
- Treat docstring as a Markdown text, not as a reStructuredText.

Correct:

```python
class Foo:
    """
    One-sentence summary.

    Optional extended explanation of the why, not the what.
    """
    
    def __init__(self, value: str) -> None:
        """
        Set up a Foo class.
        
        Args:
            value: Instance representation.
        """
        
        self.value = value

    def bar(self) -> None:
        """
        Does the thing.
        """
        
        self.baz(self.value)

    @staticmethod
    def baz(value: str) -> None:
        """
        Prints the value.
        
        Args:
            value: Value for print.
        """
        import pprint

        pprint.pprint(value)
```

Incorrect:

```python
class Foo:
    """One-sentence summary.

    Optional extended explanation of the why, not the what.
    
    Attributes:
        value: Instance representation.
    """  # opening is not on separate line, attributes are the same as __init__'s args
    
    def __init__(self, value: str) -> None:
        """
        Set up a Foo class
        
        Args:
            value: Instance representation.
        """  # no period in the first line
        
        self.value = value

    def bar(self) -> None:
        """Does the thing."""  # one-line docstring
        self.baz(self.value)  # no empty line
    
    @staticmethod
    def baz(value) -> None:
        """
        Prints the value.
        
        Args:
            value (str): Value for print
        """  # type hint in docstring
    
        import pprint  # extra blank line before "import" and missing blank line after
        pprint.pprint(value)
```
