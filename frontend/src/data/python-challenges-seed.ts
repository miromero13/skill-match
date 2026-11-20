import type { ChallengePayload } from "@/types/programming"

export type ChallengeSeedTemplate = Omit<
  ChallengePayload,
  "skill_id" | "level_number" | "evaluation_modality" | "execution_profile"
>

const makeChallenge = (
  title: string,
  statement: string,
  starter_code: string,
  tests: [string, string, string, "PUBLIC" | "HIDDEN"][]
): ChallengeSeedTemplate => ({
  title,
  statement,
  starter_code,
  time_limit_ms: 2000,
  memory_limit_mb: 128,
  max_output_bytes: 65536,
  allowed_imports: [],
  blocked_imports: [],
  tests: tests.map(([name, stdin_data, expected_stdout, visibility], order_index) => ({
    name,
    stdin_data,
    expected_stdout,
    visibility,
    order_index,
  })),
})

/**
 * 20 retos semilla de Python (lectura por stdin y salida por stdout) para pruebas del sandbox.
 */
export const PYTHON_CHALLENGES_SEED: ChallengeSeedTemplate[] = [
  makeChallenge(
    "Suma de dos números",
    "Leé dos números enteros (uno por línea) e imprimí su suma.",
    "def solve():\n    a = int(input())\n    b = int(input())\n    # Imprimí la suma\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Positivos", "3\n5\n", "8", "PUBLIC"],
      ["Con negativo", "-4\n10\n", "6", "HIDDEN"],
      ["Ceros", "0\n0\n", "0", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Número par o impar",
    "Leé un número entero e imprimí 'PAR' si es par o 'IMPAR' si es impar.",
    "def solve():\n    n = int(input())\n    # Tu código aquí\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Número par", "4\n", "PAR", "PUBLIC"],
      ["Número impar", "7\n", "IMPAR", "HIDDEN"],
      ["Cero", "0\n", "PAR", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Mayor de tres números",
    "Leé tres enteros (uno por línea) e imprimí el mayor de los tres.",
    "def solve():\n    a = int(input())\n    b = int(input())\n    c = int(input())\n    # Imprimí el mayor\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Orden creciente", "2\n9\n5\n", "9", "PUBLIC"],
      ["Negativos", "-10\n-3\n-7\n", "-3", "HIDDEN"],
      ["Iguales", "4\n4\n4\n", "4", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Invertir cadena de texto",
    "Leé una línea de texto e imprimila invertida.",
    "def solve():\n    texto = input()\n    # Imprimí el texto invertido\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Palabra simple", "python\n", "nohtyp", "PUBLIC"],
      ["Con espacios", "hola mundo\n", "odnum aloh", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Contar vocales",
    "Leé una cadena de texto e imprimí cuántas vocales (a, e, i, o, u, sin distinguir mayúsculas) contiene.",
    "def solve():\n    texto = input()\n    # Contá las vocales\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Minúsculas", "programacion\n", "5", "PUBLIC"],
      ["Mayúsculas y minúsculas", "Python Es Genial\n", "5", "HIDDEN"],
      ["Sin vocales", "rhythm\n", "0", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Suma de 1 a N",
    "Leé un entero positivo N e imprimí la suma de todos los enteros desde 1 hasta N inclusive.",
    "def solve():\n    n = int(input())\n    # Imprimí la suma de 1 a n\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["N pequeño", "5\n", "15", "PUBLIC"],
      ["N = 1", "1\n", "1", "HIDDEN"],
      ["N = 100", "100\n", "5050", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Factorial de un número",
    "Leé un entero no negativo N e imprimí su factorial (N!). Recordá que 0! = 1.",
    "def solve():\n    n = int(input())\n    # Calculá el factorial\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Factorial de 5", "5\n", "120", "PUBLIC"],
      ["Factorial de 0", "0\n", "1", "HIDDEN"],
      ["Factorial de 7", "7\n", "5040", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Palíndromo",
    "Leé una palabra (sin espacios) e imprimí 'SI' si es palíndromo (ignorando mayúsculas) o 'NO' en caso contrario.",
    "def solve():\n    palabra = input().strip()\n    # Verificá si es palíndromo\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Es palíndromo", "Reconocer\n", "SI", "PUBLIC"],
      ["No es palíndromo", "python\n", "NO", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Suma de elementos de una lista",
    "Leé una línea con números enteros separados por espacios e imprimí su suma total.",
    "def solve():\n    nums = list(map(int, input().split()))\n    # Imprimí la suma\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Lista positiva", "1 2 3 4 5\n", "15", "PUBLIC"],
      ["Con negativos", "10 -3 2 -9\n", "0", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Contar números pares en lista",
    "Leé una línea de enteros separados por espacios e imprimí cuántos de ellos son pares.",
    "def solve():\n    nums = list(map(int, input().split()))\n    # Contá los pares\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Mixto", "1 2 3 4 6\n", "3", "PUBLIC"],
      ["Ninguno par", "1 3 5 7\n", "0", "HIDDEN"],
      ["Negativos pares", "-2 -4 5\n", "2", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Promedio de calificaciones",
    "Leé una línea de números separados por espacios e imprimí el promedio redondeado a 2 decimales (formato {:.2f}).",
    "def solve():\n    notas = list(map(float, input().split()))\n    # Calculá e imprimí el promedio con 2 decimales\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Enteros exactos", "10 20 30\n", "20.00", "PUBLIC"],
      ["Con decimales", "7.5 8.5 9.0\n", "8.33", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Eliminar duplicados manteniendo orden",
    "Leé una línea de enteros separados por espacios e imprimí los valores únicos separados por un espacio, conservando el orden de primera aparición.",
    "def solve():\n    nums = input().split()\n    # Eliminá duplicados manteniendo el orden\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Con repetidos", "3 1 3 2 1 4\n", "3 1 2 4", "PUBLIC"],
      ["Todos iguales", "5 5 5\n", "5", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Celsius a Fahrenheit",
    "Leé una temperatura en grados Celsius e imprimí su equivalente en Fahrenheit con 1 decimal (F = C * 9/5 + 32).",
    "def solve():\n    c = float(input())\n    # Convertí a Fahrenheit con 1 decimal\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Punto de congelación", "0\n", "32.0", "PUBLIC"],
      ["Cien grados", "100\n", "212.0", "HIDDEN"],
      ["Negativo", "-40\n", "-40.0", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Tabla de multiplicar (1 al 5)",
    "Leé un entero N e imprimí en una sola línea sus múltiplos del 1 al 5 separados por espacios (N*1 N*2 N*3 N*4 N*5).",
    "def solve():\n    n = int(input())\n    # Imprimí los 5 múltiplos\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Tabla del 3", "3\n", "3 6 9 12 15", "PUBLIC"],
      ["Tabla del 0", "0\n", "0 0 0 0 0", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Contar palabras",
    "Leé una oración e imprimí la cantidad de palabras que contiene.",
    "def solve():\n    linea = input()\n    # Contá las palabras\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Oración normal", "Hola mundo desde Python\n", "4", "PUBLIC"],
      ["Espacios extra", "  uno   dos  tres \n", "3", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Máximo y mínimo de una lista",
    "Leé una línea de enteros separados por espacios e imprimí el mínimo y el máximo separados por un espacio.",
    "def solve():\n    nums = list(map(int, input().split()))\n    # Imprimí min y max\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Varios números", "8 3 15 1 9\n", "1 15", "PUBLIC"],
      ["Un solo número", "42\n", "42 42", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Número primo",
    "Leé un entero N e imprimí 'PRIMO' si es primo o 'NO PRIMO' si no lo es (recordá que 1 y menores no son primos).",
    "def solve():\n    n = int(input())\n    # Verificá si n es primo\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Primo", "7\n", "PRIMO", "PUBLIC"],
      ["Compuesto", "9\n", "NO PRIMO", "HIDDEN"],
      ["Caso 1", "1\n", "NO PRIMO", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Suma de dígitos",
    "Leé un entero positivo N e imprimí la suma de todos sus dígitos.",
    "def solve():\n    n = input().strip()\n    # Sumá los dígitos\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Tres dígitos", "123\n", "6", "PUBLIC"],
      ["Con ceros", "9005\n", "14", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "FizzBuzz unitario",
    "Leé un entero N. Imprimí 'FizzBuzz' si es múltiplo de 3 y 5, 'Fizz' si solo de 3, 'Buzz' si solo de 5, o el número N en otro caso.",
    "def solve():\n    n = int(input())\n    # Lógica FizzBuzz\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Múltiplo de 3 y 5", "15\n", "FizzBuzz", "PUBLIC"],
      ["Solo de 3", "9\n", "Fizz", "HIDDEN"],
      ["Solo de 5", "10\n", "Buzz", "HIDDEN"],
      ["Ninguno", "7\n", "7", "HIDDEN"],
    ]
  ),
  makeChallenge(
    "Segundo mayor de una lista",
    "Leé una línea con al menos dos enteros distintos separados por espacios e imprimí el segundo mayor valor único.",
    "def solve():\n    nums = list(map(int, input().split()))\n    # Encontrá el segundo mayor único\n\nif __name__ == \"__main__\":\n    solve()",
    [
      ["Sin repetidos", "10 5 20 8\n", "10", "PUBLIC"],
      ["Con repetidos", "4 9 9 2\n", "4", "HIDDEN"],
    ]
  ),
]
