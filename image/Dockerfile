FROM public.ecr.aws/lambda/python:3.11

# WORKDIR /app

# Install system dependencies
RUN yum update -y && \
    yum install -y \
    file-devel \
    poppler-utils \
    gcc \
    python3-devel \
    postgresql-devel \
    && yum clean all && \
    rm -rf /var/cache/yum

# Copy requirements and install Python dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/

# Create necessary directories
# RUN mkdir -p logs uploads
RUN mkdir -p /tmp/logs /tmp/uploads

ENV PYTHONPATH="${LAMBDA_TASK_ROOT}"
ENV AWS_LAMBDA_FUNCTION_NAME=true
# Expose port
# EXPOSE 8000
CMD [ "lambda_handler.lambda_handler" ]
# Run the application
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]