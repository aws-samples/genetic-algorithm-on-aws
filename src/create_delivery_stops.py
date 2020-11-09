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
import boto3

# A simple app to populate a DynamoDB table with location data for the Genetic Algorithm example

dynamodb = boto3.resource('dynamodb')

DELIVERY_STOPS_TABLE = 'ga-blog-stack-DeliveryStops'
table = dynamodb.Table(DELIVERY_STOPS_TABLE)

def write_delivery_stops(stops_set_id, stops):
    item = {
        'StopsSetID': stops_set_id,
        'Locations': stops
    }
    table.put_item(Item=item)

def build_list_of_stops():
    stops = []
    coords_used = set()
    coords_used.add("0+0")  # don't allow a stop at (0,0) since that's the warehouse

    NUM_STOPS = 100
    MIN_X = -15
    MAX_X = 15
    MIN_Y = -15
    MAX_Y = 15

    for _ in range(NUM_STOPS):
        key = ""
        while True:
            x_coord = random.randint(MIN_X, MAX_X)
            y_coord = random.randint(MIN_Y, MAX_Y)
            key = str(x_coord) + "+" + str(y_coord)
            if key not in coords_used:
                break
        coords_used.add(key)

        stop = {'X': x_coord, 'Y': y_coord}
        stops.append(stop)

    return stops

if __name__ == "__main__":
    stops = build_list_of_stops()
    print(stops)
    write_delivery_stops(0, stops)
