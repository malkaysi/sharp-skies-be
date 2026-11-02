FROM public.ecr.aws/lambda/python:3.13

COPY lambdas/stack_worker/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY app/__init__.py ${LAMBDA_TASK_ROOT}/app/__init__.py
COPY app/services/ ${LAMBDA_TASK_ROOT}/app/services/
COPY lambdas/stack_worker/handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
