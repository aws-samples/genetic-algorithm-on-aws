#!/bin/sh -e

# Be sure to update the following line with your ECR repo name
ECR_REPO='ACCTNUMBER.dkr.ecr.REGION.amazonaws.com/REPONAME'
IMAGE='ga-optimal-path'

docker build -t ${IMAGE} .
docker tag ${IMAGE} ${ECR_REPO}

# Be sure to update the following line with your region, if you aren't using us-east-2
eval "$(aws ecr get-login --no-include-email --region us-east-2)"
docker push ${ECR_REPO}
