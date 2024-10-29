import aws_cdk as core
import aws_cdk.assertions as assertions

from nice_dcv_with_gateway.nice_dcv_with_gateway_stack import NiceDcvWithGatewayStack


# example tests. To run these tests, uncomment this file along with the example
# resource in nice_dcv_with_gateway/nice_dcv_with_gateway_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = NiceDcvWithGatewayStack(app, "nice-dcv-with-gateway")
    template = assertions.Template.from_stack(stack)


#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
