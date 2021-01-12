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
import random
import copy
import math
import boto3
from botocore.exceptions import ClientError
import multiprocessing
import time
import datetime
import json
import uuid
import argparse
import sys

####################################################################################
# Genetic algorithm parameters
####################################################################################
POPULATION_SIZE = 5000
CROSSOVER_RATE = 1.0
ELITISM_RATE = 0.05
MUTATION_RATE = 0.25
TOURNEY_SIZE = 3
MAX_STAGNANT_GENERATIONS = 100
MAX_GENERATIONS = 1000

####################################################################################
# Problem-specific variables
####################################################################################
STARTING_WAREHOUSE_X = 0
STARTING_WAREHOUSE_Y = 0

delivery_stop_locations = []

DELIVERY_STOPS_TABLE = 'ga-blog-stack-DeliveryStops'
RESULTS_TABLE = 'ga-blog-stack-Results'

dynamodb = boto3.resource('dynamodb')
stops_table = dynamodb.Table(DELIVERY_STOPS_TABLE)
result_table = dynamodb.Table(RESULTS_TABLE)

####################################################################################
# The data structure to store a potential solution
####################################################################################
class CandidateSolution(object):
    def __init__(self):
        self.fitness_score = 0

        # the order to follow, initially completely random.
        # each item is simply an index into the delivery_stop_locations list,
        # which specifies the exact X,Y location
        num_stops = len(delivery_stop_locations)
        self.path = list(range(num_stops))
        random.shuffle(self.path)

    def __repr__(self):
        return f'Score {self.fitness_score}: {self.path[:5]}'

####################################################################################
# Utility functions
####################################################################################

def load_delivery_stops():
    # load the stops (each of which includes an X and Y coord), using Set 0 (the only set loaded at this point)
    stops = None
    try:
        response = stops_table.get_item(Key={'StopsSetID': 0})
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        stops = response['Item']['Locations']
        print(f'Loaded {len(stops)} delivery stops')
        for delivery_stop in stops:
            delivery_stop['X'] = int(delivery_stop['X'])
            delivery_stop['Y'] = int(delivery_stop['Y'])

    return stops

def calc_score_for_candidate(candidate):
    # start with the distance from the warehouse to the first stop
    warehouse_location = {'X': STARTING_WAREHOUSE_X, 'Y': STARTING_WAREHOUSE_Y}
    sum = dist(warehouse_location, delivery_stop_locations[candidate.path[0]])

    # then travel to each stop
    for i in range(len(candidate.path) - 1):
        sum += dist(delivery_stop_locations[candidate.path[i]], delivery_stop_locations[candidate.path[i + 1]])

    # then travel back to the warehouse
    sum += dist(warehouse_location, delivery_stop_locations[candidate.path[-1]])
    return sum

def dist(location_a, location_b):
    # for this problem, we are assuming a grid of streets where each delivery stop is located at an intersection.
    # this means that travelling from one to another is the delta X + delta Y distance.
    # (this problem assumes all streets are two-way)
    xdiff = abs(location_a['X'] - location_b['X'])
    ydiff = abs(location_a['Y'] - location_b['Y'])
    return xdiff + ydiff


def create_random_initial_population():
    print('Creating gen0')
    population = []
    for _ in range(POPULATION_SIZE):
        population.append(CandidateSolution())
    return population

def tourney_select(population):
    # we use Tourney selection here, which is nothing more than selecting X
    # candidates and using the best one.  It's the fastest selection method
    # available, and strikes a nice balance between randomness and leaning
    # towards quality.  Increase the tourney size to lean more towards quality.
    # Decrease the tourney size (to a minimum of 1) to increase genetic
    # diversity (aka randomness).
    selected = random.sample(population, TOURNEY_SIZE)
    best = min(selected, key=lambda c: c.fitness_score)
    return best

def select_parents(population):
    # using Tourney selection, get two candidates and make sure they're distinct
    while True:
        candidate1 = tourney_select(population)
        candidate2 = tourney_select(population)
        if candidate1 != candidate2:
            break
    return candidate1, candidate2

def crossover_parents_to_create_children(parent_one, parent_two):
    child1 = copy.deepcopy(parent_one)
    child2 = copy.deepcopy(parent_two)

    # sometimes we don't cross over, so use copies of the parents
    if random.random() >= CROSSOVER_RATE:
        return child1, child2

    num_genes = len(parent_one.path)
    start_cross_at = random.randint(0, num_genes - 2)  # pick a point between 0 and the end - 2, so we can cross at least 1 stop
    num_remaining = num_genes - start_cross_at
    end_cross_at = random.randint(num_genes - num_remaining + 1, num_genes - 1)

    for index in range(start_cross_at, end_cross_at + 1):
        child1_stop = child1.path[index]
        child2_stop = child2.path[index]

        # if the same, skip it since there is no crossover needed at this gene
        if child1_stop == child2_stop:
            continue

        # find within child1 and swap
        first_found_at = child1.path.index(child1_stop)
        second_found_at = child1.path.index(child2_stop)
        child1.path[first_found_at], child1.path[second_found_at] = child1.path[second_found_at], child1.path[first_found_at]

        # and the same for the second child
        first_found_at = child2.path.index(child1_stop)
        second_found_at = child2.path.index(child2_stop)
        child2.path[first_found_at], child2.path[second_found_at] = child2.path[second_found_at], child2.path[first_found_at]

    return child1, child2


def mutate_candidate_maybe(candidate):
    # mutation doesn't happen every time, so first check if we should do it:
    if random.random() >= MUTATION_RATE:
        return

    # there are two methods to mutate a candidate: simple swapping of 2 randomly-selected locations,
    # or a randomly-selected displacement, which moves one location to a new spot in the candidate,
    # shifting everything else up.  We split the mutation types evenly, 50% for each.
    # The type of mutation to use is strongly dependent on the type of problem you are solving.
    randval = random.random()
    if randval < 0.5:
        swap_mutation(candidate)
    else:
        displacement_mutation(candidate)

def swap_mutation(candidate):
    indexes = range(len(candidate.path))
    pos1, pos2 = random.sample(indexes, 2)
    candidate.path[pos1], candidate.path[pos2] = candidate.path[pos2], candidate.path[pos1]

def displacement_mutation(candidate):
    num_stops = len(candidate.path)
    stop_to_move = random.randint(0, num_stops - 1)
    insert_at = random.randint(0, num_stops - 1)
    # make sure it's moved to a new index within the path, so it's really different
    while insert_at == stop_to_move:
        insert_at = random.randint(0, num_stops - 1)
    stop_index = candidate.path[stop_to_move]
    del candidate.path[stop_to_move]
    candidate.path.insert(insert_at, stop_index)

def check_candidate_validity(candidate):
    assert len(candidate.path) == 100, "Wrong number of elements in list"
    uniq_stops = set(candidate.path)
    assert len(uniq_stops) == 100, "Non-unique elements in list"

def write_best_solution_to_dynamodb(candidate):
    guid = str(uuid.uuid4())
    ddb_data = json.loads('{}')
    ddb_data['GUID'] = guid
    ddb_data['Completed'] = datetime.datetime.now().strftime('%c')
    ddb_data['Path'] = candidate.path
    ddb_data['Score'] = candidate.fitness_score
    ddb_data['Pop'] = POPULATION_SIZE
    ddb_data['Crossover'] = str(CROSSOVER_RATE)
    ddb_data['Elitism'] = str(ELITISM_RATE)
    ddb_data['Mutation'] = str(MUTATION_RATE)
    ddb_data['Tourney'] = TOURNEY_SIZE
    ddb_data['NumStops'] = len(delivery_stop_locations)
    result_table.put_item(Item=ddb_data)
    return guid

def write_per_generation_scores(guid, per_generation_best_scores):
    # this function is helpful for debugging purposes, since it shows the progression
    # of the GA over time.  It's not needed for the main functioning.
    outfile_path = f'results/{guid}_score-per_gen.csv'
    f = open(outfile_path, "w")
    gen = 0
    for score in per_generation_best_scores:
        gen += 1
        f.write(f'{gen}, {score}')
        f.write("\n")
    f.close()

####################################################################################
# The engine of the Genetic Algorithm
####################################################################################

def find_best_path():
    current_generation = create_random_initial_population()
    generation_number = 1

    best_distance_all_time = 99999999
    best_candidate_all_time = None
    best_solution_generation_number = 0
    per_generation_best_scores = []

    # the multiprocessing code doesn't work on Windows
    use_multiprocessing = "win" not in sys.platform
    pool = multiprocessing.Pool()

    job_start_time = time.time()

    while True:

        generation_start_time = time.time()

        uniq_scores = set()

        if use_multiprocessing:
            # this function calls calc_score_for_candidate for each member of current_generation,
            # then combines the results into the scores list:
            scores = pool.map(calc_score_for_candidate, current_generation)
            for index, candidate in enumerate(current_generation):
                candidate.fitness_score = scores[index]
                uniq_scores.add(candidate.fitness_score)
        else:
            for candidate in current_generation:
                # check_candidate_validity(candidate)
                candidate.fitness_score = calc_score_for_candidate(candidate)
                uniq_scores.add(candidate.fitness_score)

        num_uniq_fitness_scores = len(uniq_scores)

        # find the best one this generation
        best_candidate_this_generation = min(current_generation, key=lambda c: c.fitness_score)
        per_generation_best_scores.append(best_distance_all_time)

        # did this generation give us a new all-time best?
        if best_candidate_this_generation.fitness_score < best_distance_all_time:
            # make a copy, since the best candidate of this generation may be used
            # in later generations (and therefore possibly modified)
            best_candidate_all_time = copy.deepcopy(best_candidate_this_generation)
            best_distance_all_time = best_candidate_this_generation.fitness_score
            best_solution_generation_number = generation_number
        else:
            # have we gone many generations without improvement?  If so, we should exit
            if (generation_number - best_solution_generation_number) >= MAX_STAGNANT_GENERATIONS:
                break

        # alternatively, if we've hit the maximum number of generations, exit
        if generation_number > MAX_GENERATIONS:
            break

        # now create the next generation, starting with elites
        num_elites = int(ELITISM_RATE * POPULATION_SIZE)
        current_generation.sort(key=lambda c: c.fitness_score)
        next_generation = [current_generation[i] for i in range(num_elites)]

        # then populate the rest of the next generation
        num_to_add = POPULATION_SIZE - num_elites
        for _ in range(num_to_add):
            parent1, parent2 = select_parents(current_generation)
            child1, child2 = crossover_parents_to_create_children(parent1, parent2)
            mutate_candidate_maybe(child1)
            next_generation.append(child1)
            mutate_candidate_maybe(child2)
            next_generation.append(child2)

        # print per-generation stats
        gen_num_str = '{:>4}'.format(generation_number)
        low_score_str = '{:>6}'.format(str(best_distance_all_time))
        duration = '{:4.1f}'.format(time.time() - generation_start_time)
        uniq_str = '{:>4}'.format(num_uniq_fitness_scores)
        print(f'Gen {gen_num_str}   best: {low_score_str}   uniq: {uniq_str}   dur: {duration}s ')

        # now that the next generation is ready, replace the current generation with it
        current_generation = next_generation
        generation_number += 1

    # we drop out of the loop once we go stagnant, or hit a maximum number of generations
    job_total_time = time.time() - job_start_time
    total_minutes = '{:6.1f}'.format(job_total_time / 60.0)
    print(f'Job complete.  Total duration: {total_minutes} min over {generation_number - 1} generations')

    return best_candidate_all_time, per_generation_best_scores

if __name__ == "__main__":
    # handle arguments
    ap = argparse.ArgumentParser()
    ap.add_argument('-m', '--maxstops', required=False, default='100', help="How many stops to use (default 100)")
    ap.add_argument('-c', '--crossover', required=False, default='0.50', help="Crossover rate (default 0.50)")
    ap.add_argument('-e', '--elitism', required=False, default='0.10', help="Elitism rate (default 0.10)")
    ap.add_argument('-u', '--mutation', required=False, default='0.10', help="Mutation rate (default 0.10)")
    ap.add_argument('-t', '--tourney', required=False, default='2', help="Tourney size (default 2)")
    args = vars(ap.parse_args())

    CROSSOVER_RATE = float(args.get("crossover"))
    ELITISM_RATE = float(args.get("elitism"))
    MUTATION_RATE = float(args.get("mutation"))
    TOURNEY_SIZE = int(args.get("tourney"))

    print('')
    print(f'Crossover: {CROSSOVER_RATE}  Elitism: {ELITISM_RATE} Mutation: {MUTATION_RATE} Tourney: {TOURNEY_SIZE}')

    delivery_stop_locations = load_delivery_stops()
    num_stops = int(args.get("maxstops"))
    delivery_stop_locations = delivery_stop_locations[:num_stops]

    best, per_generation_best_scores = find_best_path()
    guid = write_best_solution_to_dynamodb(best)

    # the following is useful when debugging on a local machine, but not helpful when run via Batch:
    # write_per_generation_scores(guid, per_generation_best_scores)
