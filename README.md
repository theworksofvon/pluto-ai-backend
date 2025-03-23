# Pluto AI

Pluto AI is a comprehensive machine learning service that includes a FastAPI server to facilitate predictions using trained linear regression models and also fine-tuned LLMs. As a base LLM, Pluto leverages local deepseek models 7b and 14b, also it can leverage openai's models. This document will guide you through each part of the prediction process, including how the FastAPI server interacts with the machine learning agent.

## Prediction Process

### 1. Data Collection
The first step in the prediction process is collecting the relevant data. This data can come from various sources such as databases, APIs, or user input. We created a data pipeline to collect data directly from the nba's api and also odds api for gambling lines. We aggregate this data and store it in a local csv file that is referenced in later modules.

In this step we create some new features that will be used in training such as **rolling_fga_5** and others.
**reference: pluto-ai/impl/pluto-ai/src/scripts/create_dataset.py**

### 2. Data Preprocessing
Once the data is collected, it needs to be preprocessed. This involves:
- **Cleaning**: Removing any missing or inconsistent data.
- **Normalization**: Scaling the data to a standard range.
- **Feature Engineering**: Creating new features or modifying existing ones to improve the model's performance.
- **Storing Data**: We store the preprocessed data in a local csv file that is referenced in later modules.

### 3. Training the Linear RegressionModel
With the preprocessed data and selected model, the next step is to train the model. This involves feeding the data into the model and allowing it to learn the patterns and relationships within the data.
In this step, we use the `LinearRegression` class from the `sklearn` library to train the model.
**reference: pluto-ai/impl/pluto-ai/src/scripts/linear_regression_model.py**

### 4. Model Evaluation
After training the model, evaluate its performance using metrics such as accuracy, precision, recall, and F1 score. This helps in understanding how well the model is performing and if any adjustments are needed. We run simple testing to check the model's performance inside the `linear_regression_model.py` file. This is not a comprehensive evaluation, but it gives us a good idea of the model's performance.
**reference: pluto-ai/impl/pluto-ai/src/scripts/linear_regression_model.py**

### 5. FastAPI Server Setup
Pluto AI includes a FastAPI server that acts as an interface for making predictions. The server is set up to handle incoming requests, process the data, and return predictions. The server endpoints are designed to:
- **Receive Data**: Accept input data in JSON format.
- **Process Data**: Preprocess the input data as required.
- **Invoke the Model**: Use the trained model to make predictions.
- **Return Results**: Send back the prediction results in a structured format.

### 6. Making Predictions
Once the FastAPI server is running, you can make predictions by sending HTTP requests to the server with the input data. The server will process the request, use the machine learning agent and data analytics pipeline to generate predictions, and return the results.

### 7. Model Deployment
