import type { QuestionContent } from "@/services/theory-bank-service"

const openQ = (
  prompt: string,
  reference_answer: string,
  criteria: QuestionContent["criteria"],
  time_limit_seconds = 90
): QuestionContent => ({
  kind: "OPEN",
  prompt,
  choices: [],
  correct_choice: null,
  reference_answer,
  criteria,
  time_limit_seconds,
  max_score: 20,
})

const mcQ = (
  prompt: string,
  choices: [string, string][],
  correct_choice: string,
  reference_answer: string,
  description: string
): QuestionContent => ({
  kind: "MULTIPLE_CHOICE",
  prompt,
  choices: choices.map(([code, text]) => ({ code, text })),
  correct_choice,
  reference_answer,
  criteria: [{ name: "Selección y fundamento", weight: 100, description }],
  time_limit_seconds: 60,
  max_score: 20,
})

const tfQ = (
  prompt: string,
  correct_choice: "TRUE" | "FALSE",
  reference_answer: string,
  description: string
): QuestionContent => ({
  kind: "TRUE_FALSE",
  prompt,
  choices: [
    { code: "TRUE", text: "Verdadero" },
    { code: "FALSE", text: "Falso" },
  ],
  correct_choice,
  reference_answer,
  criteria: [{ name: "Respuesta y justificación", weight: 100, description }],
  time_limit_seconds: 60,
  max_score: 20,
})

/**
 * 50 reactivos semilla de Python Principiante (Nivel 1) para pruebas del banco.
 */
export const PYTHON_NIVEL1_QUESTIONS: QuestionContent[] = [
  // 1-10: Variables, tipos y operadores
  openQ(
    "Explicá la diferencia principal entre una lista (list) y una tupla (tuple) en Python.",
    "Las listas son mutables (se pueden modificar después de crearlas), mientras que las tuplas son inmutables (no se pueden alterar tras su creación).",
    [
      { name: "Mutabilidad", weight: 60, description: "Distingue lista mutable y tupla inmutable." },
      { name: "Uso o sintaxis", weight: 40, description: "Menciona corchetes/paréntesis o cuándo usar cada una." },
    ]
  ),
  mcQ(
    "¿Cuál es la palabra clave correcta para definir una función en Python?",
    [["A", "function"], ["B", "def"], ["C", "func"], ["D", "define"]],
    "B",
    "En Python se usa 'def' seguido del nombre de la función y paréntesis.",
    "Elige 'def' y explica cómo se declara una función."
  ),
  tfQ(
    "En Python, la indentación es obligatoria para delimitar bloques de código como condicionales o bucles.",
    "TRUE",
    "Verdadero. Python usa la indentación para definir el alcance de los bloques; si falta o es inconsistente lanza IndentationError.",
    "Confirma Verdadero y explica el rol de la indentación."
  ),
  openQ(
    "¿Qué diferencia hay entre el operador '=' y el operador '==' en Python?",
    "'=' es el operador de asignación (guarda un valor en una variable), mientras que '==' es el operador de comparación de igualdad (devuelve True o False).",
    [
      { name: "Asignación", weight: 50, description: "Explica correctamente el uso de '='." },
      { name: "Comparación", weight: 50, description: "Explica correctamente el uso de '=='." },
    ]
  ),
  mcQ(
    "¿Qué resultado produce la expresión 7 // 2 en Python?",
    [["A", "3.5"], ["B", "3"], ["C", "1"], ["D", "4"]],
    "B",
    "El operador '//' realiza división entera (floor division), descartando la parte decimal, por lo que 7 // 2 es 3.",
    "Identifica la división entera y su resultado 3."
  ),
  mcQ(
    "¿Qué operador calcula el resto (módulo) de una división en Python?",
    [["A", "/"], ["B", "//"], ["C", "%"], ["D", "**"]],
    "C",
    "El operador '%' devuelve el residuo o resto de la división entre dos números.",
    "Selecciona '%' y explica qué es el módulo."
  ),
  tfQ(
    "En Python, los nombres de variables distinguen entre mayúsculas y minúsculas (case-sensitive).",
    "TRUE",
    "Verdadero. 'edad' y 'Edad' son dos variables completamente distintas en Python.",
    "Confirma Verdadero y da un ejemplo o explicación breve."
  ),
  mcQ(
    "¿Qué devuelve la expresión 2 ** 3 en Python?",
    [["A", "6"], ["B", "8"], ["C", "5"], ["D", "9"]],
    "B",
    "El operador '**' calcula la potencia, por lo que 2 ** 3 equivale a 2 elevado a la 3, es decir, 8.",
    "Identifica '**' como potencia y obtiene 8."
  ),
  openQ(
    "¿Qué representa el valor especial None en Python?",
    "None representa la ausencia de valor o un valor nulo; es el único objeto de tipo NoneType y suele usarse para inicializar variables o indicar que una función no retorna un valor explícito.",
    [
      { name: "Significado", weight: 60, description: "Explica que indica ausencia de valor." },
      { name: "Ejemplo de uso", weight: 40, description: "Menciona retorno por defecto de funciones o inicialización." },
    ]
  ),
  tfQ(
    "En Python es obligatorio declarar el tipo de dato de una variable antes de asignarle un valor.",
    "FALSE",
    "Falso. Python es de tipado dinámico; el tipo se infiere en tiempo de ejecución al asignar el valor.",
    "Responde Falso y menciona el tipado dinámico."
  ),

  // 11-20: Strings y E/S
  openQ(
    "¿Qué hace la función incorporada len() y sobre qué tipos de datos puede aplicarse?",
    "len() devuelve la cantidad de elementos o caracteres de un objeto como str, list, tuple, dict o set.",
    [
      { name: "Propósito", weight: 50, description: "Indica que retorna la longitud o cantidad de elementos." },
      { name: "Tipos válidos", weight: 50, description: "Nombra al menos dos tipos como str, list, dict o tuple." },
    ]
  ),
  mcQ(
    "¿Qué tipo de dato devuelve siempre la función input() en Python?",
    [["A", "int"], ["B", "str"], ["C", "bool"], ["D", "float"]],
    "B",
    "input() siempre retorna una cadena de texto (str), por lo que para operar numéricamente hay que convertirla con int() o float().",
    "Selecciona 'str' y aclara la necesidad de conversión para números."
  ),
  tfQ(
    "Las cadenas de texto (str) en Python son inmutables.",
    "TRUE",
    "Verdadero. No se puede modificar un carácter de un string directamente; las operaciones de texto crean una nueva cadena.",
    "Confirma Verdadero y explica que no se pueden modificar in-place."
  ),
  mcQ(
    "¿Qué método de string elimina los espacios en blanco al inicio y al final de una cadena?",
    [["A", ".split()"], ["B", ".strip()"], ["C", ".trim()"], ["D", ".clean()"]],
    "B",
    "El método .strip() elimina espacios (y saltos de línea) al principio y al final de un string.",
    "Elige '.strip()' y describe su efecto."
  ),
  openQ(
    "¿Cómo funcionan los f-strings en Python y qué ventaja ofrecen?",
    "Se escriben anteponiendo 'f' antes de las comillas (ej. f'Hola {nombre}') y permiten interpolar variables o expresiones directamente dentro de la cadena de forma legible y rápida.",
    [
      { name: "Sintaxis", weight: 50, description: "Menciona el prefijo f y las llaves {}." },
      { name: "Ventaja", weight: 50, description: "Explica la interpolación legible de expresiones." },
    ]
  ),
  mcQ(
    "¿Qué devuelve 'hola mundo'.split()?",
    [["A", "['hola', 'mundo']"], ["B", "'holamundo'"], ["C", "('hola', 'mundo')"], ["D", "10"]],
    "A",
    ".split() sin argumentos divide la cadena usando espacios como separador y devuelve una lista de strings.",
    "Identifica que devuelve la lista ['hola', 'mundo']."
  ),
  tfQ(
    "En Python, intentar sumar un int y un str con '+' (por ejemplo, 5 + '3') convierte automáticamente el texto en número.",
    "FALSE",
    "Falso. Python es fuertemente tipado y lanza un TypeError si se intenta sumar int y str sin conversión explícita.",
    "Responde Falso y menciona el error TypeError."
  ),
  mcQ(
    "¿Qué función permite conocer el tipo de dato de una variable en Python?",
    [["A", "typeof()"], ["B", "kind()"], ["C", "type()"], ["D", "datatype()"]],
    "C",
    "La función incorporada type(x) devuelve el tipo o clase del objeto x.",
    "Selecciona 'type()' correctamente."
  ),
  openQ(
    "¿Para qué sirve la función int() y qué ocurre si se llama con int('abc')?",
    "int() convierte números o cadenas numéricas válidas a enteros. Si recibe 'abc' (una cadena no numérica), lanza una excepción ValueError.",
    [
      { name: "Conversión", weight: 50, description: "Explica que convierte valores a entero." },
      { name: "Error", weight: 50, description: "Indica que falla con ValueError ante texto inválido." },
    ]
  ),
  tfQ(
    "El comentario de una sola línea en Python comienza con el símbolo '#'.",
    "TRUE",
    "Verdadero. Todo lo que sigue a '#' en una línea es ignorado por el intérprete de Python.",
    "Confirma Verdadero respecto al uso de '#' para comentarios."
  ),

  // 21-30: Listas, tuplas, diccionarios y sets
  tfQ(
    "En Python, los índices de una lista comienzan en 1.",
    "FALSE",
    "Falso. Python usa indexación base cero, por lo que el primer elemento está en el índice 0.",
    "Responde Falso y aclara que el primer índice es 0."
  ),
  mcQ(
    "¿Qué hace el índice negativo -1 al acceder a una lista, por ejemplo mi_lista[-1]?",
    [["A", "Lanza IndexError"], ["B", "Devuelve el primer elemento"], ["C", "Devuelve el último elemento"], ["D", "Invierte la lista"]],
    "C",
    "Los índices negativos cuentan desde el final de la secuencia; -1 accede al último elemento.",
    "Selecciona el último elemento y explica la indexación negativa."
  ),
  mcQ(
    "¿Qué método agrega un único elemento al final de una lista?",
    [["A", ".add()"], ["B", ".append()"], ["C", ".push()"], ["D", ".insert_end()"]],
    "B",
    ".append(x) añade x al final de la lista modificándola in-place.",
    "Elige '.append()' correctamente."
  ),
  openQ(
    "¿Cuál es la diferencia entre .append() y .extend() en una lista?",
    ".append(x) agrega x como un único elemento al final (si x es una lista, queda anidada), mientras que .extend(iterable) agrega cada elemento del iterable individualmente al final.",
    [
      { name: "append", weight: 50, description: "Explica que agrega un solo elemento." },
      { name: "extend", weight: 50, description: "Explica que concatena todos los elementos del iterable." },
    ]
  ),
  mcQ(
    "¿Qué estructura de datos almacena pares clave-valor (key-value)?",
    [["A", "list"], ["B", "set"], ["C", "dict"], ["D", "tuple"]],
    "C",
    "El diccionario (dict) asocia claves únicas e inmutables con valores.",
    "Selecciona 'dict' y explica el concepto clave-valor."
  ),
  openQ(
    "¿Qué ventaja tiene usar diccionario.get('clave', valor_defecto) frente a diccionario['clave']?",
    "Si la clave no existe, diccionario['clave'] lanza KeyError, mientras que .get() devuelve None (o el valor por defecto indicado) sin interrumpir el programa.",
    [
      { name: "Comportamiento de []", weight: 50, description: "Menciona que [] lanza KeyError si falta la clave." },
      { name: "Comportamiento de .get()", weight: 50, description: "Explica que .get() retorna None o un valor por defecto." },
    ]
  ),
  tfQ(
    "Un conjunto (set) en Python permite almacenar elementos duplicados conservando el orden de inserción.",
    "FALSE",
    "Falso. Un set almacena únicamente elementos únicos (elimina duplicados) y no garantiza orden posicional por índice.",
    "Responde Falso y explica la unicidad de los sets."
  ),
  mcQ(
    "¿Cómo se obtiene una sublista con los elementos desde el índice 1 hasta el 3 (sin incluir el 4) de una lista L?",
    [["A", "L[1:4]"], ["B", "L[1:3]"], ["C", "L[0:3]"], ["D", "L(1,4)"]],
    "A",
    "En slicing L[inicio:fin], el índice 'inicio' es inclusivo y el índice 'fin' es exclusivo, por lo que L[1:4] toma los índices 1, 2 y 3.",
    "Elige L[1:4] y explica que el límite superior es exclusivo."
  ),
  openQ(
    "¿Qué hace el operador 'in' cuando se usa con una lista o un diccionario?",
    "Verifica pertenencia y devuelve True o False. En una lista comprueba si el valor está presente; en un diccionario comprueba si la clave existe entre sus claves.",
    [
      { name: "En listas", weight: 50, description: "Explica que busca si existe el elemento." },
      { name: "En diccionarios", weight: 50, description: "Aclara que busca entre las claves." },
    ]
  ),
  mcQ(
    "¿Qué método de lista elimina y devuelve el último elemento (o el elemento en un índice dado)?",
    [["A", ".remove()"], ["B", ".pop()"], ["C", ".clear()"], ["D", ".del()"]],
    "B",
    ".pop() extrae y retorna el último elemento de la lista (o el de la posición indicada).",
    "Selecciona '.pop()' correctamente."
  ),

  // 31-40: Condicionales y bucles
  mcQ(
    "¿Qué palabra clave se usa en Python para encadenar una condición alternativa después de 'if'?",
    [["A", "else if"], ["B", "elif"], ["C", "elseif"], ["D", "when"]],
    "B",
    "Python utiliza la contracción 'elif' para evaluar condiciones adicionales tras un 'if'.",
    "Selecciona 'elif' correctamente."
  ),
  openQ(
    "¿Cuál es la diferencia principal entre un bucle 'for' y un bucle 'while' en Python?",
    "El bucle 'for' itera sobre los elementos de una secuencia o iterable (cantidad conocida de pasos), mientras que 'while' repite el bloque mientras una condición lógica sea verdadera.",
    [
      { name: "Bucle for", weight: 50, description: "Explica iteración sobre secuencias/iterables." },
      { name: "Bucle while", weight: 50, description: "Explica repetición condicionada a una expresión booleana." },
    ]
  ),
  mcQ(
    "¿Qué secuencia de números genera range(1, 5)?",
    [["A", "1, 2, 3, 4, 5"], ["B", "1, 2, 3, 4"], ["C", "0, 1, 2, 3, 4"], ["D", "2, 3, 4, 5"]],
    "B",
    "range(inicio, fin) incluye 'inicio' y excluye 'fin', generando 1, 2, 3 y 4.",
    "Elige 1, 2, 3, 4 y explica que el límite superior es exclusivo."
  ),
  openQ(
    "¿En qué se diferencian las sentencias 'break' y 'continue' dentro de un bucle?",
    "'break' termina inmediatamente la ejecución completa del bucle, mientras que 'continue' salta el resto de la iteración actual y pasa directamente a la siguiente iteración.",
    [
      { name: "break", weight: 50, description: "Explica que corta el bucle por completo." },
      { name: "continue", weight: 50, description: "Explica que omite la iteración actual y continúa." },
    ]
  ),
  tfQ(
    "En Python, una lista vacía [] evaluada en un condicional 'if' se considera False (falsy).",
    "TRUE",
    "Verdadero. Colecciones vacías ([], {}, (), ''), 0 y None se evalúan como falsy en contextos booleanos.",
    "Confirma Verdadero y menciona valores falsy."
  ),
  mcQ(
    "¿Qué devuelve la expresión True and False or True?",
    [["A", "False"], ["B", "True"], ["C", "None"], ["D", "Error de sintaxis"]],
    "B",
    "'and' tiene mayor precedencia que 'or': (True and False) es False, y False or True da True.",
    "Selecciona True y explica la evaluación lógica."
  ),
  openQ(
    "¿Qué es un bucle infinito con 'while' y cómo se evita o detiene?",
    "Ocurre cuando la condición del while nunca pasa a ser False. Se evita actualizando la variable de control dentro del bucle o usando 'break' ante una condición de salida.",
    [
      { name: "Causa", weight: 50, description: "Explica que la condición permanece siempre verdadera." },
      { name: "Prevención", weight: 50, description: "Menciona actualizar la condición o usar break." },
    ]
  ),
  tfQ(
    "El bucle 'for' en Python puede recorrer directamente los caracteres de un string sin usar índices numéricos.",
    "TRUE",
    "Verdadero. Los strings son iterables, por lo que 'for c in texto:' recorre carácter por carácter.",
    "Confirma Verdadero explicando que str es iterable."
  ),
  mcQ(
    "¿Qué función incorporada permite iterar sobre una lista obteniendo a la vez el índice y el valor?",
    [["A", "zip()"], ["B", "enumerate()"], ["C", "index()"], ["D", "range()"]],
    "B",
    "enumerate(iterable) devuelve pares (índice, elemento) en cada iteración.",
    "Selecciona 'enumerate()' correctamente."
  ),
  openQ(
    "¿Para qué sirve la palabra clave 'pass' en Python?",
    "'pass' es una sentencia nula que no hace nada; se utiliza como marcador de posición donde la sintaxis exige un bloque indentado (por ejemplo, una función o condicional aún vacío).",
    [
      { name: "Comportamiento", weight: 50, description: "Indica que no ejecuta ninguna acción." },
      { name: "Utilidad", weight: 50, description: "Explica que evita errores de sintaxis en bloques vacíos." },
    ]
  ),

  // 41-50: Funciones, alcance y errores básicos
  openQ(
    "¿Qué diferencia hay entre usar 'print()' y usar 'return' dentro de una función?",
    "print() solo muestra un texto por consola pero no entrega el dato al código que llamó la función; return finaliza la función y devuelve un valor reutilizable al llamador.",
    [
      { name: "print()", weight: 50, description: "Explica que solo imprime en pantalla." },
      { name: "return", weight: 50, description: "Explica que devuelve un valor al código llamador." },
    ]
  ),
  mcQ(
    "Si una función en Python no tiene sentencia 'return', ¿qué valor devuelve por defecto?",
    [["A", "0"], ["B", "False"], ["C", "None"], ["D", "''"]],
    "C",
    "Toda función sin return explícito (o con return sin valor) devuelve None automáticamente.",
    "Elige None correctamente."
  ),
  tfQ(
    "Una variable definida dentro de una función (variable local) puede leerse directamente desde fuera de esa función sin retornarla.",
    "FALSE",
    "Falso. Las variables definidas dentro de una función tienen alcance local y no existen fuera de ella (lanzan NameError).",
    "Responde Falso y explica el alcance local."
  ),
  openQ(
    "¿Qué son los parámetros con valor por defecto en una función de Python?",
    "Son parámetros a los que se les asigna un valor inicial en la definición (ej. def saludar(nombre='Invitado'):), de modo que si el llamador omite ese argumento se usa el valor predeterminado.",
    [
      { name: "Definición", weight: 60, description: "Explica cómo se declaran con '=' en def." },
      { name: "Comportamiento", weight: 40, description: "Indica que son opcionales al invocar la función." },
    ]
  ),
  mcQ(
    "¿Qué excepción se produce al intentar acceder a un índice que no existe en una lista?",
    [["A", "KeyError"], ["B", "IndexError"], ["C", "ValueError"], ["D", "NameError"]],
    "B",
    "Acceder a una posición fuera del rango de la lista lanza IndexError.",
    "Selecciona IndexError correctamente."
  ),
  mcQ(
    "¿Qué excepción lanza Python cuando se intenta usar una variable que no fue definida previamente?",
    [["A", "TypeError"], ["B", "NameError"], ["C", "SyntaxError"], ["D", "AttributeError"]],
    "B",
    "Referenciar un identificador no definido en el ámbito actual produce NameError.",
    "Selecciona NameError correctamente."
  ),
  openQ(
    "¿Para qué sirve un bloque 'try / except' en Python?",
    "Permite capturar y manejar excepciones que ocurren durante la ejecución de un bloque de código, evitando que el programa se detenga abruptamente.",
    [
      { name: "Bloque try", weight: 50, description: "Explica que envuelve el código propenso a fallar." },
      { name: "Bloque except", weight: 50, description: "Explica que captura y gestiona el error." },
    ]
  ),
  tfQ(
    "La sentencia 'import math' permite utilizar funciones matemáticas como math.sqrt() en tu archivo Python.",
    "TRUE",
    "Verdadero. 'import' carga módulos de la biblioteca estándar o de terceros para usar sus funciones y constantes.",
    "Confirma Verdadero respecto a la importación de módulos."
  ),
  mcQ(
    "¿Cuál de las siguientes opciones crea correctamente un diccionario vacío en Python?",
    [["A", "[]"], ["B", "{}"], ["C", "()"], ["D", "set()"]],
    "B",
    "Las llaves vacías '{}' crean un diccionario vacío en Python (para un conjunto vacío se usa set()).",
    "Elige '{}' y aclara que set() crea un conjunto vacío."
  ),
  openQ(
    "¿Qué diferencia existe entre '==' y 'is' al comparar dos objetos en Python?",
    "'==' compara si los valores o contenidos de ambos objetos son iguales, mientras que 'is' comprueba si ambas variables apuntan exactamente al mismo objeto en memoria.",
    [
      { name: "Igualdad de valor (==)", weight: 50, description: "Explica que == compara contenido." },
      { name: "Identidad (is)", weight: 50, description: "Explica que is compara identidad en memoria." },
    ]
  ),
]
