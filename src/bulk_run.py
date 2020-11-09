# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import os
import random

NUM_TRIALS_PER = 8

if __name__ == "__main__":
    crossover_rates = [0.5, 0.75, 1.0]
    elitism_rates = [0.05, 0.10, 0.15]
    mutation_rates = [0.10, 0.20, 0.30]
    tourney_sizes = [2, 3, 4]

    print("Building combos")
    combos = []
    for crossover in crossover_rates:
        for elitism in elitism_rates:
            for mutation in mutation_rates:
                for tourney in tourney_sizes:
                    combos.append((crossover, elitism, mutation, tourney))

    print("Shuffling")
    random.shuffle(combos)

    print("Starting trials")
    for trial_params in combos:
        crossover = trial_params[0]
        elitism = trial_params[1]
        mutation = trial_params[2]
        tourney = trial_params[3]
        for _ in range(NUM_TRIALS_PER):
            os.system(f'python genetic_algorithm.py -c {crossover} -e {elitism} -u {mutation} -t {tourney}')
