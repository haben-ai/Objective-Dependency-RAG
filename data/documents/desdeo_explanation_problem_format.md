# The Problem format

Multiobjective optimization problems are represented by pydantic dataclasses
in DESDEO. These are serializable and therefore easy to store. Moreover,
they can be readily transformed into JSON objects, which makes passing
them from DESDEO's web-API to various frontend applications seamless. This
also facilitates the parsing of the problem format into other formats as well.
While representing problems as pydantic dataclasses comes with some overhead,
this is justified by the utility and robustness of the pydantic dataclasses.

One of the challenges with this kind of representation is representing function
expression. These have been taken care by exploiting the MathJSON format, which
is described in more details in the section
[The MathJSONformat](#the-mathjson-format). The pydantic dataclass for representing a
multiobjective optimization problem in DESDEO is discussed in the section
[The Problem schema](#the-problem-schema), where the structure, or schema, of the
dataclass is described in detail.

## The MathJSON format

MathJSON is a lightweight, JSON-based format designed for representing
mathematical expressions in a structured and easily parsable manner. It provides
a standardized way to represent mathematical notation within JSON objects.
Moreover, it allows users to define mathematical formulations in web-based
frontend applications, which can then be directly represented in the DESDEO
problem schema.

In DESDEO, the MathJSON format is utilized to represent function
expression found throughout the problem schema. MathJSON follows
Polish notation, which means that mathematical operators precede
the operands when defining mathematical expressions. As an example,
consider the following expression:

$$
\max(x, y ,z) + \frac{y}{z} - \sin\left(z^x + 4.2\right)^3,
$$

where x, y, and x are some variables. The equivalent of this
expression in the MathJSON format (Polish notation), would be:

```json
[
  "Add",
  ["Divide", "y", "z"],
  ["Max", "x", "y", "z"],
  [
    "Negate",
    ["Power", ["Sin", ["Add", ["Power", "z", "x"], 4.2]], 3]
  ]
]
```

At first glance, this may look overly complicated, but from a programming
perspective, parsing Polish notation is much simpler than infix notation,
e.g., "normal" notation, where the operations are between the operands.

The MathJSON notation is utilized for all function expressions found
in the problem schema in DESDEO. For more information on the MathJSON
format, see the [MathJSON project](https://cortexjs.io/math-json/).


## The Problem schema

Here, the structure of the problem dataclass, or the schema, is presented
in detail. The `Problem` dataclass itself is constructed from other dataclasses
contained in its field.  We will refer to the schemas as _models_ from thereon.

### The symbol field

Across many of the models found in the `Problem` dataclass, the field `symbol`
will be often present. This field is very important, because it is utilized
to identify variables and function expression across the `Problem` model.
Therefore, the `symbol` field should contain a symbol that is unique across the
whole `Problem` model. The symbol itself is nothing more than a string value.
Some symbol names are reserved in DESDEO, and users should avoid defining
variables or function expression with these symbols. Reserved symbols
are discussed in the section [Symbols and expressions](#symbols-and-expressions).

### The scenario keys field

As with the `symbol` field, the `scenario_keys` is also a recurring field
across the `Problem` model. This field is used to indicate to which scenario,
or scenarios, a field (e.g., representing an objective function) belongs to.
The `scenario_keys` is a list of strings and is optional. When its value
is `None` is means that it belongs to all defined scenarios, or no
scenarios at all if the problem has no defined scenarios. The `Problem`
model itself has also the field `scenario_keys`, which is used indicate
which scenarios haven been defined for the `Problem`. When this field
is `None`, it means the `Problem` has no defined scenarios.

### Common fields for computable models

The computable models that are used to construct a `Problem` all have some common
fields defined for them. The computable models are `Objective`, `Constraint`,
`ExtraFunction`, and `ScalarizationFunction`. These fields generally
represent something that can be evaluated, and is likely to be optimized at some
point, either directly, or indirectly, e.g., as part of a scalarization.
The common fields are:

  - `is_linear`: is the model linear?
  - `is_convex`: is the model convex?
  - `is_twice_differentiable`: is the model twice continuously differentiable?

These are all assumed to be `False` by default. The listed fields play an important
role in the selection of optimizer when the `Problem` model is being solved.

### Problem

The main dataclass storing information related to a multiobjective optimization is the
`Problem` model, which consists of other models. 
The `Problem` model itself consists of the following fields:

  - `name`: the name of the problem,
  - `description`: the description of the problem,
  - `constants`: a list of constant utilized in the definition of the problem,
  - `variables`: a list of the variables of the problem,
  - `objectives`: a list of the objective functions of the problem,
  - `constraints`: an optional list of the constraints of the problem,
  - `extra_funcs`: an optional list of extra functions utilized in defining the problem, 
  - `scalarization_funcs`: an optional list of scalarized representations of the problem,
  - `discrete_representation`: an optional representation of the problem as discrete decision variable vector and objective vector pairs, and
  - `scenario_keys`: an optional list of scenario keys.

The **name** and **description** of the problem are just strings. The other fields consist of one or
more additional models, or Python types, such as lists. These will be described next.

<div class="admonition note">
<p class="admonition-title">Note</p>
<p>
    The <tt>symbol</tt> entries across all fields must be unique. If one or more
    non-unique symbols are defined, <tt>Problem</tt> will raise an error when being
    initialized.
</p>
</div>

<div class="admonition note">
<p class="admonition-title">Note</p>
<p>
    The <tt>Problem</tt> model and all its field are <bf>immutable</bf>. The only exception to this
    is the <tt>symbol</tt> field of the <tt>ScalarizationFunction</tt> models. 
</p>
</div>


### Constant

The `Constant` model defines a constant with the fields `name`, `symbol` and
`value`. The field `name` is the name of the constant, for example "Price", the `symbol`
is the constant's mathematical symbol, for example "c_1", and the `value`
represents the numerical value of the constant, for example 4.2. The
JSON schema of `Constant` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "description": "Model for a constant.",
  "properties": {
    "name": {
      "description": "Descriptive name of the constant. This can be used in UI and visualizations. Example: 'maximum cost'.",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "description": "Symbol to represent the constant. This will be used in the rest of the problem definition. It may also be used in UIs and visualizations. Example: 'c_1'.",
      "title": "Symbol",
      "type": "string"
    },
    "value": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        }
      ],
      "description": "The value of the constant.",
      "title": "Value"
    }
  },
  "required": [
    "name",
    "symbol",
    "value"
  ],
  "title": "Constant",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "name": "constant example",
  "symbol": "c",
  "value": 42.1
}

```
</details>
</br>



### TensorConstant

The `TensorConstant` model defines an indexed constant with the fields
`name`, `symbol`, `shape`, and `values`. The `name is the name of the
constant, for example "Weights", the `symbol` is the constant's mathematical
symbol, for example "A", `shape` defines the sizes of the dimensions of the
constant, and `values` defines the values represented by the constant.
`TensorConstant` is an indexed value, which means it can represent
tensors, such as vectors and matrices.

The JSON schema of `TensorConstant` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "$defs": {
    "Tensor": {
      "anyOf": [
        {
          "items": {
            "$ref": "/$defs/Tensor"
          },
          "type": "array"
        },
        {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "integer"
              },
              {
                "type": "boolean"
              }
            ]
          },
          "type": "array"
        },
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "const": "List",
          "enum": [
            "List"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "description": "Model for a tensor containing constant values.",
  "properties": {
    "name": {
      "description": "Descriptive name of the tensor representing the values. E.g., 'distances'",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "description": "Symbol to represent the constant. This will be used in the rest of the problem definition. Notice that the elements of the tensor will be represented with the symbol followed by indices. E.g., the first element of the third element of a 2-dimensional tensor, is represented by 'x_1_3', where 'x' is the symbol given to the TensorVariable. Note that indexing starts from 1.",
      "title": "Symbol",
      "type": "string"
    },
    "shape": {
      "description": "A list of the dimensions of the tensor, e.g., `[2, 3]` would indicate a matrix with 2 rows and 3 columns.",
      "items": {
        "type": "integer"
      },
      "title": "Shape",
      "type": "array"
    },
    "values": {
      "$ref": "/$defs/Tensor",
      "description": "A list of lists, with the elements representing the values of each constant element in the tensor. E.g., `[[5, 22, 0], [14, 5, 44]]`."
    }
  },
  "required": [
    "name",
    "symbol",
    "shape",
    "values"
  ],
  "title": "TensorConstant",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json
{
  "name": "tensor constant example",
  "symbol": "t_c",
  "shape": [
    2
  ],
  "values": [
    "List",
    40,
    50
  ]
}

```
</details>
</br>




### Variable

The `Variable` model defines a decision variable with the fields
`name`, `symbol`, `variable_type`, `lowerbound`,
`upperbound`, and `initial_value`.
The `name` and `symbol` represent the name and mathematical symbol of the variable.
The field `variable_type` represents the variable's type, either "real", "integer",
or "binary". Lastly, the `initial_value` field is the initial value of the variable. This
can be used by some optimizers found in DESDEO in finding an optimal solution
to, e.g., a scalarized variant of the problem. The JSON schema
`Variable` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "$defs": {
    "VariableTypeEnum": {
      "description": "An enumerator for possible variable types.",
      "enum": [
        "real",
        "integer",
        "binary"
      ],
      "title": "VariableTypeEnum",
      "type": "string"
    }
  },
  "description": "Model for a variable.",
  "properties": {
    "name": {
      "description": "Descriptive name of the variable. This can be used in UI and visualizations. Example: 'velocity'.",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "description": "Symbol to represent the variable. This will be used in the rest of the problem definition. It may also be used in UIs and visualizations. Example: 'v_1'.",
      "title": "Symbol",
      "type": "string"
    },
    "variable_type": {
      "$ref": "/$defs/VariableTypeEnum",
      "description": "Type of the variable. Can be real, integer or binary."
    },
    "lowerbound": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Lower bound of the variable.",
      "title": "Lowerbound"
    },
    "upperbound": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Upper bound of the variable.",
      "title": "Upperbound"
    },
    "initial_value": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Initial value of the variable. This is optional.",
      "title": "Initial Value"
    }
  },
  "required": [
    "name",
    "symbol",
    "variable_type"
  ],
  "title": "Variable",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "name": "variable example",
  "symbol": "x",
  "variable_type": "real",
  "lowerbound": 0,
  "upperbound": 1,
  "initial_value": 0.5
}

```
</details>
</br>

### TensorVariable

The `TensorVariable` model defines a decision variable with the fields
`name`, `symbol`, `variable_type`, `shape`, `lowerbounds`,
`upperbounds`, and `initial_values`.
The `name` and `symbol` represent the name and mathematical symbol of the variable.
The field `variable_type` represents the variable's element types, either "real", "integer",
or "binary". Lastly, the `initial_values` field defines the initial values contained in the 
variable. This
information can be used by some optimizers found in DESDEO in finding an optimal solution
to, e.g., a scalarized variant of the problem the variable is part of.
`TensorVariable` is an indexed value, which means it can represent
tensors, such as vectors and matrices.

The JSON schema
`TensorVariable` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "$defs": {
    "Tensor": {
      "anyOf": [
        {
          "items": {
            "$ref": "/$defs/Tensor"
          },
          "type": "array"
        },
        {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "integer"
              },
              {
                "type": "boolean"
              }
            ]
          },
          "type": "array"
        },
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "const": "List",
          "enum": [
            "List"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ]
    },
    "VariableTypeEnum": {
      "description": "An enumerator for possible variable types.",
      "enum": [
        "real",
        "integer",
        "binary"
      ],
      "title": "VariableTypeEnum",
      "type": "string"
    }
  },
  "description": "Model for a tensor, e.g., vector variable.",
  "properties": {
    "name": {
      "description": "Descriptive name of the variable. This can be used in UI and visualizations. Example: 'velocity'.",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "description": "Symbol to represent the variable. This will be used in the rest of the problem definition. Notice that the elements of the tensor will be represented with the symbol followed by indices. E.g., the first element of the third element of a 2-dimensional tensor, is represented by 'x_1_3', where 'x' is the symbol given to the TensorVariable. Note that indexing starts from 1.",
      "title": "Symbol",
      "type": "string"
    },
    "variable_type": {
      "$ref": "/$defs/VariableTypeEnum",
      "description": "Type of the variable. Can be real, integer, or binary. Note that each element of a TensorVariable is assumed to be of the same type."
    },
    "shape": {
      "description": "A list of the dimensions of the tensor, e.g., `[2, 3]` would indicate a matrix with 2 rows and 3 columns.",
      "items": {
        "type": "integer"
      },
      "title": "Shape",
      "type": "array"
    },
    "lowerbounds": {
      "anyOf": [
        {
          "$ref": "/$defs/Tensor"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A list of lists, with the elements representing the lower bounds of each element. E.g., `[[1, 2, 3], [4, 5, 6]]`. If a single value is supplied, that value is assumed to be the lower bound of each element. Defaults to None."
    },
    "upperbounds": {
      "anyOf": [
        {
          "$ref": "/$defs/Tensor"
        },
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A list of lists, with the elements representing the upper bounds of each element.  E.g., `[[1, 2, 3], [4, 5, 6]]`. If a single value is supplied, that value is assumed to be the upper bound of each element. Defaults to None.",
      "title": "Upperbounds"
    },
    "initial_values": {
      "anyOf": [
        {
          "$ref": "/$defs/Tensor"
        },
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A list of lists, with the elements representing the initial values of each element.  E.g., `[[1, 2, 3], [4, 5, 6]]`. If a single value is supplied, that value is assumed to be the initial value of each element. Defaults to None.",
      "title": "Initial Values"
    }
  },
  "required": [
    "name",
    "symbol",
    "variable_type",
    "shape"
  ],
  "title": "TensorVariable",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "name": "tensor variable example",
  "symbol": "X",
  "variable_type": "integer",
  "shape": [
    3
  ],
  "lowerbounds": [
    "List",
    1,
    2,
    3
  ],
  "upperbounds": [
    "List",
    10,
    20,
    30
  ],
  "initial_values": [
    "List",
    1,
    1,
    1
  ]
}

```
</details>
</br>



### Objective

The `Objective` model defines an objective function with the fields `name`, `symbol`, `func`, 
`maximized`, `ideal`, `nadir`, and `objective_type`. The `name` and `symbol`
represent the objective's name and mathematical symbol. The field
`func` represents the objective's mathematical, or analytical, formulation.
This can be given either in the MathJSON format, or it may also be supplied
in infix, e.g., "normal", notation. In the case of the latter, the expression
will be parsed into the MathJSON format. The field `maximized` indicated
whether the objective function is to be maximized or not. By default, this
field is assumed to be false, i.e., objective functions are assumed to be
minimized in DESDEO unless it is explicitly specified that maximization
is desired. The fields `ideal` and `nadir` are the objective function's
ideal and nadir points, respectively. These are also optional, but supplying
them, if known, can expedite the execution of some methods in DESDEO. Lastly,
`objective_type` is the type of the objective functions. Currently, this can be
either "analytical" or "data_based". In the latter case, the `func` field
may be left empty, but it is then expected that a `DiscreteRepresentation`
for the objective is available in the `Problem` model. See the
subsection [DiscreteRepresentation](#discreterepresentation).

The JSON schema of `Objective` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "$defs": {
    "ObjectiveTypeEnum": {
      "description": "An enumerator for supported objective function types.",
      "enum": [
        "analytical",
        "data_based",
        "simulator",
        "surrogate"
      ],
      "title": "ObjectiveTypeEnum",
      "type": "string"
    }
  },
  "description": "Model for an objective function.",
  "properties": {
    "name": {
      "description": "Descriptive name of the objective function. This can be used in UI and visualizations. Example: 'time'.",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "description": "Symbol to represent the objective function. This will be used in the rest of the problem definition. It may also be used in UIs and visualizations. Example: 'f_1'.",
      "title": "Symbol",
      "type": "string"
    },
    "unit": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The unit of the objective function. This is optional. Used in UIs and visualizations. Example: 'seconds' or 'millions of hectares'.",
      "title": "Unit"
    },
    "func": {
      "anyOf": [
        {
          "items": {},
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The objective function. This is a JSON object that can be parsed into a function.Must be a valid MathJSON object. The symbols in the function must match the symbols defined for variable/constant/extra function. Can be 'None' for 'data_based', 'simulator' or 'surrogate' objective functions. If 'None', either 'simulator_path' or 'surrogates' must not be 'None'.",
      "title": "Func"
    },
    "simulator_path": {
      "anyOf": [
        {
          "format": "path",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Path to a python file with the connection to simulators. Must be a valid Path.Can be 'None' for 'analytical', 'data_based' or 'surrogate' objective functions.If 'None', either 'func' or 'surrogates' must not be 'None'.",
      "title": "Simulator Path"
    },
    "surrogates": {
      "anyOf": [
        {
          "items": {
            "format": "path",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A list of paths to models saved on disk. Can be 'None' for 'analytical', 'data_based or 'simulator' objective functions. If 'None', either 'func' or 'simulator_path' must not be 'None'.",
      "title": "Surrogates"
    },
    "maximize": {
      "default": false,
      "description": "Whether the objective function is to be maximized or minimized.",
      "title": "Maximize",
      "type": "boolean"
    },
    "ideal": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Ideal value of the objective. This is optional.",
      "title": "Ideal"
    },
    "nadir": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Nadir value of the objective. This is optional.",
      "title": "Nadir"
    },
    "objective_type": {
      "$ref": "/$defs/ObjectiveTypeEnum",
      "default": "analytical",
      "description": "The type of objective function. 'analytical' means the objective function value is calculated based on 'func'. 'data_based' means the objective function value should be retrieved from a table. In case of 'data_based' objective function, the 'func' field is ignored. Defaults to 'analytical'."
    },
    "is_linear": {
      "default": false,
      "description": "Whether the function expression is linear or not. Defaults to `False`.",
      "title": "Is Linear",
      "type": "boolean"
    },
    "is_convex": {
      "default": false,
      "description": "Whether the function expression is convex or not (non-convex). Defaults to `False`.",
      "title": "Is Convex",
      "type": "boolean"
    },
    "is_twice_differentiable": {
      "default": false,
      "description": "Whether the function expression is twice differentiable or not. Defaults to `False`",
      "title": "Is Twice Differentiable",
      "type": "boolean"
    },
    "scenario_keys": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional. The keys of the scenarios the objective function belongs to.",
      "title": "Scenario Keys"
    }
  },
  "required": [
    "name",
    "symbol"
  ],
  "title": "Objective",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "name": "objective example",
  "symbol": "f",
  "unit": null,
  "func": [
    "Add",
    "x",
    1
  ],
  "simulator_path": null,
  "surrogates": null,
  "maximize": false,
  "ideal": null,
  "nadir": null,
  "objective_type": "analytical",
  "is_linear": true,
  "is_convex": false,
  "is_twice_differentiable": false,
  "scenario_keys": null
}

```
</br>
</details>




### Constraint

The `Constraint` model defines a constraint function with the fields `name`,
`symbol`, `cons_type`, `linear` and `func`.  The `name` and `symbol` represent
the constraint's name and mathematical symbol, respectively. The field
`cons_type` represents the type of constraint. Currently, the type can be
either "<=" for inequality constraints, or "=" for equality constraints.
Lastly, `func` is the mathematical representation of the constraint function.
This can be supplied either in the MathJSON format or in "normal" infix format.
As for how the constraint should be defined, see the note below.

<div class="admonition note">
<p class="admonition-title">Note</p>
<p>
    The constraint is expected in a standard format where the function expression of the constraint is on the left hand side of an
    inequality expression, and on the right hand side a zero is assumed. Likewise, for equality constraints, the left hand side has a function
    expression that must be equal to zero. In other words, a constraint, such as `x_1 <= 5` must first be expressed as `x_1 - 5 <= 0`, and then the
    constraint expression supplied to the `Constraint` model would be `x_1 - 5`. Likewise, an equality constraint, such as `x_1 + x_2 == 5` would be first
    expressed as `x_1 + x_2 - 5 == 0`, and the supplied function expression would be `x_1 + x_2 - 5`.
</p>
</div>

Its JSON schema of `Constraint` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "$defs": {
    "ConstraintTypeEnum": {
      "description": "An enumerator for supported constraint expression types.",
      "enum": [
        "=",
        "<="
      ],
      "title": "ConstraintTypeEnum",
      "type": "string"
    }
  },
  "description": "Model for a constraint function.",
  "properties": {
    "name": {
      "description": "Descriptive name of the constraint. This can be used in UI and visualizations. Example: 'maximum length'.",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "description": "Symbol to represent the constraint. This will be used in the rest of the problem definition. It may also be used in UIs and visualizations. Example: 'g_1'.",
      "title": "Symbol",
      "type": "string"
    },
    "cons_type": {
      "$ref": "/$defs/ConstraintTypeEnum",
      "description": "The type of the constraint. Constraints are assumed to be in a standard form where the supplied 'func' expression is on the left hand side of the constraint's expression, and on the right hand side a zero value is assume. The comparison between the left hand side and right hand side is either and quality comparison ('=') or lesser than equal comparison ('<=')."
    },
    "func": {
      "anyOf": [
        {
          "items": {},
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Function of the constraint. This is a JSON object that can be parsed into a function.Must be a valid MathJSON object. The symbols in the function must match objective/variable/constant symbols.Can be 'None' if either 'simulator_path' or 'surrogates' is not 'None'. If 'None', either 'simulator_path' or 'surrogates' must not be 'None'.",
      "title": "Func"
    },
    "simulator_path": {
      "anyOf": [
        {
          "format": "path",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Path to a python file with the connection to simulators. Must be a valid Path.Can be 'None' for if either 'func' or 'surrogates' is not 'None'.If 'None', either 'func' or 'surrogates' must not be 'None'.",
      "title": "Simulator Path"
    },
    "surrogates": {
      "anyOf": [
        {
          "items": {
            "format": "path",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A list of paths to models saved on disk. Can be 'None' for if either 'func' or 'simulator_path' is not 'None'. If 'None', either 'func' or 'simulator_path' must not be 'None'.",
      "title": "Surrogates"
    },
    "is_linear": {
      "default": true,
      "description": "Whether the constraint is linear or not. Defaults to True, e.g., a linear constraint is assumed.",
      "title": "Is Linear",
      "type": "boolean"
    },
    "is_convex": {
      "default": false,
      "description": "Whether the function expression is convex or not (non-convex). Defaults to `False`.",
      "title": "Is Convex",
      "type": "boolean"
    },
    "is_twice_differentiable": {
      "default": false,
      "description": "Whether the function expression is twice differentiable or not. Defaults to `False`",
      "title": "Is Twice Differentiable",
      "type": "boolean"
    },
    "scenario_keys": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional. The keys of the scenarios the constraint belongs to.",
      "title": "Scenario Keys"
    }
  },
  "required": [
    "name",
    "symbol",
    "cons_type"
  ],
  "title": "Constraint",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "name": "example constrant",
  "symbol": "g",
  "cons_type": "<=",
  "func": [
    "Add",
    "x",
    [
      "Negate",
      "c"
    ]
  ],
  "simulator_path": null,
  "surrogates": null,
  "is_linear": true,
  "is_convex": false,
  "is_twice_differentiable": false,
  "scenario_keys": null
}

```
</details>
</br>




### ExtraFunction

The `ExtraFunction` model defines any functions utilized in the definition of the problem. The extra function has the fields `name`,
`symbol`, and `func`. The fields `name` and `symbol` represent the extra function's name and mathematical symbol, respectively.
The field `func` is the mathematical representation of the extra function, which must be supplied either in the MathJSON
format, or in the "normal" infix notation.

The JSON schema of `ExtraFunction` looks as:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "description": "Model for extra functions.\n\nThese functions can, e.g., be functions that are re-used in the problem formulation, or\nthey are needed for other computations related to the problem.",
  "properties": {
    "name": {
      "description": "Descriptive name of the function. Example: 'normalization'.",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "description": "Symbol to represent the function. This will be used in the rest of the problem definition. It may also be used in UIs and visualizations. Example: 'avg'.",
      "title": "Symbol",
      "type": "string"
    },
    "func": {
      "anyOf": [
        {
          "items": {},
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The string representing the function. This is a JSON object that can be parsed into a function.Must be a valid MathJSON object. The symbols in the function must match symbols defined for objective/variable/constant.Can be 'None' if either 'simulator_path' or 'surrogates' is not 'None'. If 'None', either 'simulator_path' or 'surrogates' must not be 'None'.",
      "title": "Func"
    },
    "simulator_path": {
      "anyOf": [
        {
          "format": "path",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Path to a python file with the connection to simulators. Must be a valid Path.Can be 'None' for 'analytical', 'data_based' or 'surrogate' functions.If 'None', either 'func' or 'surrogates' must not be 'None'.",
      "title": "Simulator Path"
    },
    "surrogates": {
      "anyOf": [
        {
          "items": {
            "format": "path",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A list of paths to models saved on disk. Can be 'None' for 'analytical', 'data_based or 'simulator' functions. If 'None', either 'func' or 'simulator_path' must not be 'None'.",
      "title": "Surrogates"
    },
    "is_linear": {
      "default": false,
      "description": "Whether the function expression is linear or not. Defaults to `False`.",
      "title": "Is Linear",
      "type": "boolean"
    },
    "is_convex": {
      "default": false,
      "description": "Whether the function expression is convex or not (non-convex). Defaults to `False`.",
      "title": "Is Convex",
      "type": "boolean"
    },
    "is_twice_differentiable": {
      "default": false,
      "description": "Whether the function expression is twice differentiable or not. Defaults to `False`",
      "title": "Is Twice Differentiable",
      "type": "boolean"
    },
    "scenario_keys": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional. The keys of the scenario the extra functions belongs to.",
      "title": "Scenario Keys"
    }
  },
  "required": [
    "name",
    "symbol"
  ],
  "title": "ExtraFunction",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "name": "extra function example",
  "symbol": "e_f",
  "func": [
    "Multiply",
    5,
    "x"
  ],
  "simulator_path": null,
  "surrogates": null,
  "is_linear": true,
  "is_convex": true,
  "is_twice_differentiable": true,
  "scenario_keys": null
}

```
</details>
</br>




### ScalarizationFunction

The `ScalarizationFunction` model defines any scalarizations of the problem being solved. The scalarization
function has the fields `name`, `symbol` and `func`. The fields `name` and `symbol` represent the function's
name and mathematical symbol. The `func` field is the mathematical representation of the scalarization
function, it must be supplied either is the MathJSON format or "normal" infix notation.
Usually, scalarization functions are added by various methods found in DESDEO, and are not expected
to be supplied by users directly. Nevertheless, the field can be supplied by a user, if such a need arises.

Its JSON schema of `ScalarizationFunction` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "description": "Model for scalarization of the problem.",
  "properties": {
    "name": {
      "description": "Name of the scalarization function.",
      "title": "Name",
      "type": "string"
    },
    "symbol": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional symbol to represent the scalarization function. This may be used in UIs and visualizations.",
      "title": "Symbol"
    },
    "func": {
      "description": "Function representation of the scalarization. This is a JSON object that can be parsed into a function.Must be a valid MathJSON object. The symbols in the function must match the symbols defined for objective/variable/constant/extra function.",
      "items": {},
      "title": "Func",
      "type": "array"
    },
    "is_linear": {
      "default": false,
      "description": "Whether the function expression is linear or not. Defaults to `False`.",
      "title": "Is Linear",
      "type": "boolean"
    },
    "is_convex": {
      "default": false,
      "description": "Whether the function expression is convex or not (non-convex). Defaults to `False`.",
      "title": "Is Convex",
      "type": "boolean"
    },
    "is_twice_differentiable": {
      "default": false,
      "description": "Whether the function expression is twice differentiable or not. Defaults to `False`",
      "title": "Is Twice Differentiable",
      "type": "boolean"
    },
    "scenario_keys": {
      "default": null,
      "description": "Optional. The keys of the scenarios the scalarization function belongs to.",
      "items": {
        "type": "string"
      },
      "title": "Scenario Keys",
      "type": "array"
    }
  },
  "required": [
    "name",
    "func"
  ],
  "title": "ScalarizationFunction",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "name": "scalarization function example",
  "symbol": "s_f",
  "func": [
    "Multiply",
    "x",
    "e_f"
  ],
  "is_linear": false,
  "is_convex": false,
  "is_twice_differentiable": false,
  "scenario_keys": null
}

```
</details>
</br>

### DiscreteRepresentation

The `DiscreteRepresentation` model defines a discrete representation of a
problem.  This representation is defined by the decision variable and objective
function value pairs, which are defined in the fields `variable_values` and
`objective_values`, respectively.  This representation may consist of only
non-dominated solutions, or it may contain dominated solutions as well. This is
indicated by the `non_dominated` field. This representation is useful for
problems that do not have an analytical formulation. It may also be used in
conjunction with an analytical formulation. Some interactive multiobjective
optimization methods can utilize both representations, while other are better
suited just for one. For instance, NAUTILUS Navigator is best utilized with a
discrete representation.

The JSON schema `DiscreteRepresentation` looks as follows:

<details>
<summary><b>Click to expand</b></summary>

```json

{
  "description": "Model to represent discrete objective function and decision variable pairs.\n\nCan be used alongside an analytical representation as well.\n\nUsed with Objectives of type 'data_based' by default. Each of the decision\nvariable values and objective functions values are ordered in their\nrespective dict entries. This means that the decision variable values found\nat `variable_values['x_i'][j]` correspond to the objective function values\nfound at `objective_values['f_i'][j]` for all `i` and some `j`.",
  "properties": {
    "variable_values": {
      "additionalProperties": {
        "items": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "integer"
            },
            {
              "type": "boolean"
            }
          ]
        },
        "type": "array"
      },
      "description": "A dictionary with decision variable values. Each dict key points to a list of all the decision variable values available for the decision variable given in the key. The keys must match the 'symbols' defined for the decision variables.",
      "title": "Variable Values",
      "type": "object"
    },
    "objective_values": {
      "additionalProperties": {
        "items": {
          "type": "number"
        },
        "type": "array"
      },
      "description": "A dictionary with objective function values. Each dict key points to a list of all the objective function values available for the objective function given in the key. The keys must match the 'symbols' defined for the objective functions.",
      "title": "Objective Values",
      "type": "object"
    },
    "non_dominated": {
      "default": false,
      "description": "Indicates whether the representation consists of non-dominated points or not.If False, some method can employ non-dominated sorting, which might slow an interactive method down.",
      "title": "Non Dominated",
      "type": "boolean"
    }
  },
  "required": [
    "variable_values",
    "objective_values"
  ],
  "title": "DiscreteRepresentation",
  "type": "object"
}

```
</details></br>
and an example of the JSON object corresponding to the schema looks like:

</br>
<details>
<summary><b>Click to expand</b></summary>

```json

{
  "variable_values": {
    "x": [
      1
    ]
  },
  "objective_values": {
    "f": [
      1.0
    ]
  },
  "non_dominated": false
}

```
</details>
</br>



## Symbols and expressions

The field `symbol`, which is found across the `Problem` schema, plays a very important role
in DESDEO. It is utilized to identify variables, constants, and function expression. Symbols
can also be utilized across the fields of `Problem` to refer to each other. In other words,
the `func` field in a `ScalarizationModel` can contain the symbol referencing
the `func` field of an `ExtraFunction`, or the value of a `Constant`, for instance. This is
also an important fact to keep in mind when parsing the a `Problem` model from one
representation to another. This will be discussed in more detail in the 
section [Parsing and Evaluating Problems](../parsing_and_evaluating/#parsing-and-evaluating-problems).

It is assumed that any expression in a `func` field, that is not a numerical value,
refers to either a symbol or a mathematical operation. In what follows, the
reserved symbols are presented in the section [Reserved symbols](#reserved-symbols).
The supported mathematical expressions are presented in the section
[Supported Operations](#supported-operations).

### Reserved symbols

In essence, any symbol that starts with an underscore, e.g., `_x` is considered
to be reserved. This is because some of the routines in DESDEO that manipulate the
problem formulation may add, for instance, auxiliary variables, which are
automatically named with a symbol that starts with an underscore. To avoid
confusion and bugs, users are advised to avoid utilizing symbols
starting with underscores when defining problems.

Another symbol, which is should be avoided, is any symbol that ends in
`_min`, e.g., `f_1_min`. Since DESDEO internally transforms all
expressions to be optimized into their minimization form, routines will
append a `_min` to symbols to indicate that the expression the symbol
 represents, is to be, or has been, minimized. Other routines will
 expect these symbols to be available. Users are therefore advised to
 avoid symbols that end in a `_min`.

### Scalar and indexed expressions

DESDEO supports two kinds of expresssions: scalar and indexed ones. A scalar
expression represents a single value or variable, while an indexed
expression represents a collection of values or variables. For instance,
an instance of the `Variable` or `Constant` model would
represent a scalar expression, and an instance of the `TensorVariable`
or `TensorConstant` would represent an indexed expression. 

Both scalar and indexed expression may be combined, such
as taking the dot product of two indexed expressions representing
vectors and adding a scalar to it. Some operators work only
with scalar expressions, while others work with only indexed ones.
Please refer to the table in the next section for further details
on which operations support which type of expression.

<div class="admonition note">
<p class="admonition-title">Note</p>
<p>
    When modeling a problem that contains indexed expressions,
    it is important to choose a solver that supports indexed expressions.
    Please refer to the section
    <a href="../solvers/#summary-of-solvers">Summary of Solvers</a>
    for further details on which solvers support solving problems with
    indexed expressions and their operators.
</p>
</div>

### Supported Operations

Expressions representing mathematical operations are
automatically identified by DESDEO. The expressions
are case sensitive. Currently supported operations are listed
in the table below:

<div class="admonition note">
<p class="admonition-title">Note</p>
<p>
    The equivalent infix notation operator is given in parentheses.
    For operators without this equivalent, the operator will
    still work in infix notation, e.g., `Sin(x) + 3`.
</p>
</div>


| Expression  | Explanation                                 | Notes                               |
|-------------|---------------------------------------------|-------------------------------------|
| Negate (-)  | Negates the value (changes its sign).       | Element-wise for indexed expressions. Shapes must match. |
| Add (+)     | Adds two values.                            | Element-wise for indexed expressions. Shapes must match. |
| Subtract (-)| Subtracts one value from another.           | Element-wise for indexed expressions. Shapes must match. |
| Multiply (*)| Multiplies two values.                      | Element-wise for indexed expressions. Shapes must match. Indexed expression can be multiplied with a scalar where each indexed element is multiplied by the scalar's value. |
| Divide (/)  | Divides one value by another.               | Not supported for indexed expressions (use Multiply)|
| MatMul (@)  | Matrix multiplication.                      | Matrix multiplication for indexed expressions. Does not support scalar expressions.|
| Sum         | Indexed component summation.                | Sums the elements of an indexed expressions. Does not support scalar expressions.|
| Exp         | Calculates the exponential of a value.      | Indexed expressions not supported.|
| Ln          | Natural logarithm of a value.               | Indexed expressions not supported.|
| Lb          | Logarithm base 2 of a value.                | Indexed expressions not supported.|
| Lg          | Logarithm base 10 of a value.               | Indexed expressions not supported.|
| LogOnePlus  | Natural logarithm of (1 + value).           | Indexed expressions not supported.|
| Sqrt        | Square root of a value.                     | Indexed expressions not supported.|
| Square      | Squares a value.                            | Indexed expressions not supported.|
| Power (**)  | Raises a value to the power of another.     | Indexed expressions not supported.|
| Abs         | Absolute value.                             | Indexed expressions not supported.|
| Ceil        | Rounds a value up to the nearest integer.   | Indexed expressions not supported.|
| Floor       | Rounds a value down to the nearest integer. | Indexed expressions not supported.|
| Arccos      | Inverse cosine of a value.                  | Indexed expressions not supported.|
| Arccosh     | Inverse hyperbolic cosine of a value.       | Indexed expressions not supported.|
| Arcsin      | Inverse sine of a value.                    | Indexed expressions not supported.|
| Arcsinh     | Inverse hyperbolic sine of a value.         | Indexed expressions not supported.|
| Arctan      | Inverse tangent of a value.                 | Indexed expressions not supported.|
| Arctanh     | Inverse hyperbolic tangent of a value.      | Indexed expressions not supported.|
| Cos         | Cosine of a value.                          | Indexed expressions not supported.|
| Cosh        | Hyperbolic cosine of a value.               | Indexed expressions not supported.|
| Sin         | Sine of a value.                            | Indexed expressions not supported.|
| Sinh        | Hyperbolic sine of a value.                 | Indexed expressions not supported.|
| Tan         | Tangent of a value.                         | Indexed expressions not supported.|
| Tanh        | Hyperbolic tangent of a value.              | Indexed expressions not supported.|
| Max         | Finds the maximum of values.                | Indexed expressions not supported.|