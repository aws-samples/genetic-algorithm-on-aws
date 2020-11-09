# Genetic Algorithm Example on AWS
Sample code that accompanies the blog post "Using Genetic Algorithms on AWS for Optimization".  This code shows an example of a genetic algorithm that finds the shortest path that visits each delivery stop once, from a list of 100 stops.  This is an example of a classic optimization problem known as "The Travelling Salesman Problem".

This sample includes a CloudFormation template that will create all of the required infrastructure needed, including all elements that AWS Batch will use, as well as the ECR repo.  Be sure to run that first, before attempting to run the genetic algorithm.  Here's an overview of the architecture that will be created:

![Architecture Diagram](architecture.jpg)

<br/>

## Description of Included Files

| File | Purpose |
| --- | --- |
| infrastructure/template.yml | This CloudFormation template creates all of the required infrastructure, including a job definition, job queue, and compute environment for AWS Batch, as well as the associated IAM roles and required VPC, and the DynamoDB tables used (DeliveryStops and Results) |
| buildspec.yml | A file suitable for use with CI/CD via CodePipeline, CodeBuild and CodeDeploy.  Not needed if you deploy the code manually.|
| src/genetic_algorithm.py | The main code for the GA, which loads starting data from DynamoDB, performs a run, and then writes the results into the Results DynamoDB table. |
| src/bulk_run.py | This file runs the GA multiple times with various parameters.  Useful for determining which set of hyperparameters is best for this problem. |
| src/create_delivery_stops.py |  A simple app to populate a DynamoDB table with location data for the Genetic Algorithm example |
| src/deploy_image.sh | Script to build and deploy the Docker image |
| src/Dockerfile | The Dockerfile used to create a Docker image |
| src/requirements.txt | Dependencies for the Genetic Algorithm, used during Docker image build |


<br/>

## Preliminary Steps
Before running `genetic_algorithm.py`, you'll need to prepare the infrastructure.  Please follow these steps:

1. Be sure to deploy the CloudFormation stack into your account.  To do that, go to the AWS Console and navigate to the CloudFormation service.  Click on the `Create stack` button and choose `With new resources (standard)`.  On the next screen, choose `Upload a template file` and then select the template file on your local computer.  Then click on `Next`.  Then enter a name for the stack and click on `Next`, and then `Next` again.  Be sure to check the checkbox at the bottom of the page that allows CloudFormation to create IAM resources, then click on the `Create stack` button.
2. Once the CloudFormation stack is successfully created, load the delivery stop data into the corresponding DynamoDB table by running the following code:

    ```
    python create_delivery_stops.py
    ```
3.  Before running the code, be sure to update `genetic_algorithm.py` with the correct table names for the starting data, and the results.  Due to the way that the CloudFormation stack is deployed, your table names may be slightly different, so update the following lines:

    ```
    DELIVERY_STOPS_TABLE = 'ga-blog-stack-DeliveryStops'
    RESULTS_TABLE = 'ga-blog-stack-Results'
    ```

<br/>

## Running the genetic algorithm

You can run the Genetic Algorithm in two ways: directly on your desktop, or through AWS Batch.  Either way, you'll run the Python file called `genetic_algorithm.py`, which reads information about delivery stops from DynamoDB into memory, and then runs the GA until a solution is found, or until stagnation is detected.

<br/>

### Usage for genetic_algorithm.py

```sh
python genetic_algorithm.py
python genetic_algorithm.py [-m|--maxstops] [<MAXSTOPS>] [-c|--crossover] [<CROSSOVER_RATE>] [-e|--elitism] [<ELITISM_RATE>] [-u|--mutation] [<MUTATION_RATE>] [-t|--tourney] [<TOURNEY_SIZE>]
```

### Options
| Option | Default Value | Meaning |
| --- | --- | --- |
| -m | 100 | How many delivery stops to use (up to 100) |
| -c | 0.50 | Crossover rate |
| -e | 0.10 | Elitism rate |
| -u | 0.10 | Mutation rate |
| -t | 2 | Tournament size for selection |

<br/>

### Running in AWS Batch
Genetic algorithms have a large element of randomness due to the way that generation 0 is created, as well as the selection, crossover, and mutation operations.  Because of that, it's always a good idea to perform multiple runs of the application and use the best result found over those runs.

`genetic_algorithm.py` is well-suited to this since it writes the results of the run into a DynamoDB table called `Results`, which can be viewed after several runs are complete, allowing you to select the one with the best result - in this case, the shortest path found.  The resulting path is also stored in the table, which makes referencing the best solution a one-step operation.

AWS Batch is particularly helpful for this process, since it supports a concept called Array jobs, which is simply running the same code multiple times.  That code can be run in parallel or in series (depending on the limit for maximum virtual CPUs in your account), but the important concept is that the same code will be run however many times you've requested it to run.

In order to run a Batch job, the code must be placed in a Docker image, which is stored in ECR.  Instructions for packaging the code into such an image are listed below, in the section entitled "Ad-hoc Builds vs. CI/CD".

Once the code is stored in ECR, you can create a Batch job by going to the AWS Batch console.  Click on the `Create job` button, then enter a job name, select a job definition from the dropdown, select a job queue from the dropdown, and choose `Array` as the Job Type.  Finally, click on `Submit job` to initiate the job in Batch.

If you have any problems when using Batch, be sure to check the end of this document for tips about possible causes and resolutions.

<br/>

## Ad-hoc Builds vs. CI/CD
You can build and deploy the Docker image that contains the GA code manually if you wish, or you can use a Continuous Integration and Continuous Deployment (CI/CD) approach that uses AWS CodeBuild and CodePipeline.

To build and deploy manually, use the following steps:
```
# Be sure to update the following line with your own account number, region and repo name
ECR_REPO='ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPONAME'
IMAGE='ga-optimal-path'

docker build -t ${IMAGE} .
docker tag ${IMAGE} ${ECR_REPO}

# Be sure to update the following line with your region, if you are not using us-east-2
eval "$(aws ecr get-login --no-include-email --region us-east-2)"
docker push ${ECR_REPO}
```

To build using CodeBuild and CodePipeline, be sure to point the CodeBuild to the included buildspec.yml file, which is included in the `src` folder.

<br/>

## DynamoDB Tables Used
The `DeliveryStops` DynamoDB table is used to hold the input data for the GA.  It has an index field called  `StopsSetID`, which allows multiple sets of stops to be stored in the table, although for this example only set ID 0 is used.  There is only one other field in the table, called `Locations`, and that field contains a list of values that contains X and Y positions - one for each stop.

The `Results` DynamoDB table stores the results of each run.  It has an index field called `GUID` that is a random, unique value.  The other fields in the table store the date/time that the run was completed, the resulting path, the resulting score, and the settings used for Crossover, Elitism, Mutation Rate, Population used, Tournament size, and the number of delivery stops used in the problem.  Remember that the lower the score, the better the solution.

<br/>

## If your Batch job gets stuck in RUNNABLE
This can be a tricky problem.  The first thing to check is under the AWS Console, go to EC2, then click on AutoScaling Groups.  Click on the ASG listed to get more detail about the state of the job.  If you see that your account has a total vCPU limit that's lower the Desired CPUs property for the Batch Compute Environment in template.yml, lower that Desired number, or request a service increase from AWS.

Second, if you've just created a new account, there may be a delay while the account is validated, which can result in the Batch job stuck in RUNNABLE.  You can check the AutoScaling Groups (as discussed in the previous paragraph) for this condition.