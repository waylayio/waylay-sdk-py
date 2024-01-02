"""Reusable test fixtures."""
import os
import random
import math
from typing import Any, Tuple

import pytest
import pandas as pd
import numpy as np

from model_cleanup import INTEGRATION_TEST_PREFIX
from waylay import ClientCredentials, WaylayClient
from waylay.auth import WaylayCredentials, WaylayTokenAuth
from waylay.service import (
    StorageService, DataService, ResourcesService, ETLService, ByomlService, QueriesService
)


def get_test_env(key: str, default: str = None) -> str:
    """Get an environment variable."""
    test_var = os.getenv(key, default)
    if not test_var:
        raise AttributeError(f'{key} environment variable not configured, while test requires it.')
    return test_var


@pytest.fixture(scope='session')
def waylay_test_user_id():
    """Get environment variable WAYLAY_TEST_USER_ID."""
    return get_test_env('WAYLAY_TEST_USER_ID')


@pytest.fixture(scope='session')
def waylay_test_user_secret():
    """Get environment variable WAYLAY_TEST_USER_SECRET."""
    return get_test_env('WAYLAY_TEST_USER_SECRET')


@pytest.fixture(scope='session')
def waylay_test_accounts_url():
    """Get environment variable WAYLAY_TEST_ACCOUNTS_URL or 'https://accounts-api-aws.dev.waylay.io'."""
    return get_test_env('WAYLAY_TEST_ACCOUNTS_URL', 'https://accounts-api-aws.dev.waylay.io')


@pytest.fixture(scope='session')
def waylay_test_gateway_url():
    """Get environment variable WAYLAY_TEST_GATEWAY_URL or 'https://api-aws-dev.waylay.io'."""
    return get_test_env('WAYLAY_TEST_GATEWAY_URL', 'https://api-aws-dev.waylay.io')


@pytest.fixture(scope='session')
def waylay_test_client_credentials(waylay_test_user_id, waylay_test_user_secret, waylay_test_gateway_url):
    """Get client credentials.

    As specified in the environment variables
    WAYLAY_TEST_USER_ID, WAYLAY_TEST_USER_SECRET, WAYLAY_TEST_GATEWAY_URL
    """
    return ClientCredentials(
        waylay_test_user_id, waylay_test_user_secret, gateway_url=waylay_test_gateway_url
    )


@pytest.fixture(scope='session')
def waylay_test_token_string(waylay_test_client_credentials):
    """Get a valid token string."""
    token = WaylayTokenAuth(waylay_test_client_credentials).assure_valid_token()
    return token.token_string


def _create_client_from_profile_or_creds(credentials: WaylayCredentials) -> WaylayClient:
    profile = os.getenv('WAYLAY_TEST_PROFILE')
    if profile:
        return WaylayClient.from_profile(profile)
    else:
        return WaylayClient.from_credentials(credentials)


@pytest.fixture(scope='session')
def waylay_session_test_client(waylay_test_client_credentials: WaylayCredentials):
    """Get a test waylay SDK client (same for whole session)."""
    return _create_client_from_profile_or_creds(waylay_test_client_credentials)


@pytest.fixture
def waylay_test_client(waylay_test_client_credentials: WaylayCredentials):
    """Get a test waylay SDK client."""
    return _create_client_from_profile_or_creds(waylay_test_client_credentials)


@pytest.fixture
def waylay_storage(waylay_test_client: WaylayClient) -> StorageService:
    """Get the storage service."""
    return waylay_test_client.storage


@pytest.fixture
def waylay_resources(waylay_test_client: WaylayClient) -> ResourcesService:
    """Get the resources service."""
    return waylay_test_client.resources


@pytest.fixture(scope='session')
def waylay_data(waylay_session_test_client: WaylayClient) -> DataService:
    """Get the storage service."""
    return waylay_session_test_client.data


@pytest.fixture(scope='session')
def waylay_etl(waylay_session_test_client: WaylayClient) -> ETLService:
    """Get the etl service."""
    return waylay_session_test_client.etl


@pytest.fixture
def waylay_byoml(waylay_test_client: WaylayClient) -> ByomlService:
    """Get the BYOML service."""
    return waylay_test_client.byoml


@pytest.fixture(scope='session')
def waylay_queries(waylay_session_test_client: WaylayClient) -> QueriesService:
    """Get the queries service."""
    return waylay_session_test_client.queries


@pytest.fixture
def sklearn_model_and_test_data(generate_dataset) -> Tuple[Any, pd.DataFrame, np.ndarray]:
    """Get a trained sklearn model and test data."""
    df = generate_dataset

    df_train, df_validate = get_train_validation_set(df)

    # train model
    from sklearn.covariance import EllipticEnvelope   # pylint: disable=import-error
    cov_model = EllipticEnvelope(random_state=0, contamination=0.05).fit(df_train)

    predictions = cov_model.predict(df_validate)
    df_prediction = pd.DataFrame(
        predictions,
        index=df_validate.index
    )
    assert len(df_prediction.index) == len(df_validate.index)
    return cov_model, df_validate, predictions


@pytest.fixture
def generate_dataset():
    """Generate a random dataset consisting of timestamps and temperatures."""
    amount_of_samples = 2500

    data = np.random.randint(0, 25, size=(amount_of_samples, 1))
    index = pd.date_range(name='timestamp', start="2019-01-01", end="2020-12-31", periods=amount_of_samples)
    return pd.DataFrame(data, index=index, columns=['temperature'])


@pytest.fixture
def generate_labels():
    """Generate a random dataset consisting of timestamps and temperatures."""
    amount_of_samples = 2500

    data = np.random.randint(0, 5, size=(amount_of_samples, 1))
    return pd.DataFrame(data, columns=['labels'])


def get_train_validation_set(df: pd.DataFrame, split_percentage=0.8, labels: pd.DataFrame = None):
    """Split the complete dataframe in two parts."""
    train_size = int(len(df.index) * split_percentage)
    df_train = df.iloc[:train_size]
    df_validate = df.iloc[train_size:]

    if labels is not None:
        labels_train = labels.iloc[:train_size]
        labels_validate = labels.iloc[:train_size]
        return df_train, df_validate, labels_train, labels_validate

    return df_train, df_validate


@pytest.fixture
def tensorflow_model_and_test_data(
    generate_dataset,
    generate_labels
) -> Tuple[Any, pd.DataFrame, np.ndarray]:
    """Get a trained TensorFlow model and test data."""
    df = generate_dataset
    labels = generate_labels

    df_train, df_validate, labels_train, _ = get_train_validation_set(df, labels=labels)

    # Tensorflow has a lot of DeprecationWarnings, we don't want these in our test
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    warnings.filterwarnings('ignore', category=FutureWarning)

    import tensorflow as tf  # pylint: disable=import-error

    model = tf.keras.models.Sequential([
        tf.keras.layers.Flatten(input_shape=(1, 1)),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(5),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=[tf.keras.metrics.SparseCategoricalAccuracy()],
    )

    X_train = np.expand_dims(df_train, axis=2)
    X_val = np.expand_dims(df_validate, axis=2)

    model.fit(X_train, labels_train, epochs=1)

    predictions = model.predict(X_val)
    df_prediction = pd.DataFrame(
        predictions,
        index=df_validate.index
    )
    assert len(df_prediction.index) == len(df_validate.index)

    return model, df_validate, predictions


@pytest.fixture
def pytorch_model_and_test_data(
    generate_dataset,
    generate_labels
) -> Tuple[Any, pd.DataFrame, np.ndarray]:
    """Get a trained XGBoost model and test data."""
    df = generate_dataset
    labels = generate_labels

    df_train, df_validate, labels_train, _ = get_train_validation_set(df, labels=labels)

    import torch  # pylint: disable=import-error

    train_tensor = torch.tensor(df_train.values)  # pylint: disable=not-callable
    labels_tensor = torch.tensor(labels_train.values)  # pylint: disable=not-callable
    validation_tensor = torch.tensor(df_validate.values)  # pylint: disable=not-callable

    model = torch.nn.Sequential(
        torch.nn.Linear(1, 1),
        torch.nn.Flatten(1, 1)
    )

    loss_fn = torch.nn.MSELoss(reduction='sum')
    learning_rate = 1e-3
    optimizer = torch.optim.RMSprop(model.parameters(), lr=learning_rate)

    for t in range(1):
        y_pred = model(train_tensor.float())

        loss = loss_fn(y_pred, labels_tensor.float())

        optimizer.zero_grad()

        loss.backward()
        optimizer.step()

    predictions = model(validation_tensor.float())
    assert predictions.size() == validation_tensor.size()

    return model, validation_tensor, predictions.detach().numpy()


@pytest.fixture
def pytorch_custom_model_and_test_data() -> Tuple[Any, pd.DataFrame, np.ndarray]:
    """Get a trained PyTorch model and test data."""
    import torch  # pylint: disable=import-error

    class CustomReLu(torch.autograd.Function):
        """Implement a custom autograd Function."""

        @staticmethod
        def forward(context, input: torch.Tensor) -> torch.Tensor:
            context.save_for_backward(input)
            return input.clamp(min=0)

        @staticmethod
        def backward(context, grad_output: torch.Tensor) -> torch.Tensor:
            input, = context.saved_tensors
            grad_input = grad_output.clone()
            grad_input[input < 0] = 0
            return grad_input

    batch_size, input_dim = 32, 1
    dtype = torch.long  # pylint: disable=no-member

    x = torch.randn(batch_size, input_dim, dtype=dtype)  # pylint: disable=no-member

    relu = CustomReLu.apply
    script = torch.jit.trace(relu, torch.randn(batch_size, input_dim, dtype=dtype))  # pylint: disable=no-member
    local_output = relu(x)

    return relu, x, local_output.detach().numpy()


@pytest.fixture
def xgboost_model_and_test_data(
    generate_dataset,
    generate_labels
) -> Tuple[Any, pd.DataFrame, np.ndarray]:
    """Get a trained sklearn model and test data."""
    df = generate_dataset
    labels = generate_labels

    df_train, df_validate, labels_train, labels_validate = get_train_validation_set(df, labels=labels)

    # train model
    import xgboost as xgb  # pylint: disable=import-error

    dtrain = xgb.DMatrix(df_train, label=labels_train)
    dtest = xgb.DMatrix(df_validate, label=labels_validate)

    param = {
        'max_depth': 3,
        'learning_rate': 0.1,
        'colsample_bytree': 0.3,
        'objective': 'binary:hinge'
    }
    num_round = 100
    bst = xgb.train(param, dtrain, num_round)

    predictions = bst.predict(dtest)

    assert len(predictions) == len(df_validate.index)

    return bst, df_validate, predictions


@pytest.fixture
def custom_sarima_model_and_data():
    """Return model and data for a timeseries oriented model."""
    index = pd.date_range(end=pd.Timestamp.now(), periods=28, freq='1d')
    week_seasonality = [10 * math.sin((n * 2 * math.pi) / 7) + random.random() for n in range(len(index))]
    df_fit = pd.DataFrame(week_seasonality, index=index)

    import sarima_byoml_wrapper  # pylint: disable=import-error
    model_args = dict(
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 7)
    )
    model = sarima_byoml_wrapper.SARIMAXForecaster(model_args=model_args, default_window=21)
    model.fit(df_fit)
    df_predict = model.predict((df_fit, 21))
    return model, sarima_byoml_wrapper.convert_to_numpy(df_fit), sarima_byoml_wrapper.convert_to_numpy(df_predict)


@pytest.fixture(scope='session')
def integration_test_id():
    """Return a unique id to be used in the model names for integration tests."""
    return f"{INTEGRATION_TEST_PREFIX}-{os.environ.get('INTEGRATION_TEST_ID', int(random.random()*1000))}"


@pytest.fixture(scope='session')
def integration_test_session_id():
    """Return a random number up to 1000 to be used in the model names for integration tests."""
    return int(random.random()*1000)


@pytest.fixture(scope='session')
def integration_test_prefix(integration_test_id, integration_test_session_id):
    """Return a test prefix to be used in the model names for integration tests."""
    return f'{integration_test_id}-{integration_test_session_id}'
