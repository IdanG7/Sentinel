"""Example file with intentional formatting errors for PatchBot to fix."""

def badly_formatted_function(x,y,z):
    """Function with bad formatting."""
    result=x+y+z
    return result


def function_with_long_line(parameter1, parameter2, parameter3, parameter4, parameter5, parameter6, parameter7):
    """This line is too long and should be wrapped."""
    return parameter1 + parameter2 + parameter3 + parameter4 + parameter5 + parameter6 + parameter7


class BadlyFormattedClass:
    """Class with formatting issues."""
    def __init__(self,name,age,email):
        self.name=name
        self.age=age
        self.email=email

    def get_info( self ):
        """Method with weird spacing."""
        return f"{self.name} ({self.age}): {self.email}"


# Missing blank lines
class AnotherClass:
    """Another class."""
    def method1(self):
        """Method 1."""
        pass
    def method2(self):
        """Method 2."""
        pass


# Inconsistent quotes
string1 = 'single quotes'
string2 = "double quotes"
string3 = 'mixed' + "quotes"
