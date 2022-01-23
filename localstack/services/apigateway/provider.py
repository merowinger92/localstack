import logging

from localstack.aws.api import RequestContext
from localstack.aws.api.apigateway import (
    ApigatewayApi,
    ApiKeySourceType,
    Boolean,
    EndpointConfiguration,
    ListOfString,
    MapOfStringToString,
    NullableInteger,
    RestApi,
    String,
)

LOG = logging.getLogger(__name__)


class ApigatewayProvider(ApigatewayApi):
    def create_rest_api(
        self,
        context: RequestContext,
        name: String,
        description: String = None,
        version: String = None,
        clone_from: String = None,
        binary_media_types: ListOfString = None,
        minimum_compression_size: NullableInteger = None,
        api_key_source: ApiKeySourceType = None,
        endpoint_configuration: EndpointConfiguration = None,
        policy: String = None,
        tags: MapOfStringToString = None,
        disable_execute_api_endpoint: Boolean = None,
    ) -> RestApi:
        raise NotImplementedError
