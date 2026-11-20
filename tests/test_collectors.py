"""Unit tests for the three read-only collectors.

botocore's Stubber replaces the network call and validates both the request
parameters and the response shape against the real AWS service model, so a
typo in an API parameter fails here instead of in the cloud.
"""
from datetime import datetime, timedelta, timezone

import pytest
from botocore.exceptions import ClientError
from botocore.stub import ANY, Stubber

import collectors


def test_alarm_state_returns_name_reason_and_since():
    since = datetime(2026, 9, 23, 1, 9, tzinfo=timezone.utc)
    with Stubber(collectors.cloudwatch) as stub:
        stub.add_response(
            "describe_alarms",
            {"MetricAlarms": [{
                "AlarmName": "demo-AlarmLow",
                "StateReason": "Threshold crossed",
                "StateUpdatedTimestamp": since,
            }]},
            expected_params={"StateValue": "ALARM"},
        )
        result = collectors.get_alarm_state()

    assert result == [{
        "name": "demo-AlarmLow",
        "reason": "Threshold crossed",
        "since": since.isoformat(),
    }]


def test_alarm_state_with_no_alarms_returns_empty_list():
    with Stubber(collectors.cloudwatch) as stub:
        stub.add_response("describe_alarms", {"MetricAlarms": []},
                          expected_params={"StateValue": "ALARM"})
        assert collectors.get_alarm_state() == []


def test_ec2_inventory_asks_only_for_running_and_flags_untagged():
    launched = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    with Stubber(collectors.ec2) as stub:
        stub.add_response(
            "describe_instances",
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-0aaa", "InstanceType": "t3.micro", "LaunchTime": launched,
                 "Tags": [{"Key": "Name", "Value": "web"}]},
                {"InstanceId": "i-0bbb", "InstanceType": "t3.small", "LaunchTime": launched},
            ]}]},
            expected_params={"Filters": [{"Name": "instance-state-name", "Values": ["running"]}]},
        )
        result = collectors.get_ec2_inventory()

    assert [i["id"] for i in result] == ["i-0aaa", "i-0bbb"]
    assert result[0]["untagged"] is False
    assert result[1]["untagged"] is True


def _cost_group(service, amount):
    return {"Keys": [service], "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}}}


def test_yesterday_spend_totals_sorts_and_drops_dust():
    with Stubber(collectors.ce) as stub:
        stub.add_response(
            "get_cost_and_usage",
            {"ResultsByTime": [{"Groups": [
                _cost_group("Amazon VPC", "0.49"),
                _cost_group("Amazon ECS", "0.69"),
                _cost_group("Tax", "0.0004"),
            ]}]},
            expected_params={
                "TimePeriod": ANY,
                "Granularity": "DAILY",
                "Metrics": ["UnblendedCost"],
                "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
            },
        )
        result = collectors.get_yesterday_spend()

    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    assert result["date"] == yesterday.isoformat()
    # The total includes every line item, even the ones too small to list.
    assert result["total_usd"] == round(0.49 + 0.69 + 0.0004, 4)
    # Largest first, and amounts under a tenth of a cent are not listed.
    assert result["by_service"] == [
        {"service": "Amazon ECS", "usd": 0.69},
        {"service": "Amazon VPC", "usd": 0.49},
    ]


def test_yesterday_spend_lists_at_most_eight_services():
    groups = [_cost_group(f"Service {n}", str(n)) for n in range(1, 13)]
    with Stubber(collectors.ce) as stub:
        stub.add_response("get_cost_and_usage", {"ResultsByTime": [{"Groups": groups}]})
        result = collectors.get_yesterday_spend()

    assert len(result["by_service"]) == 8
    assert result["by_service"][0]["service"] == "Service 12"
    assert result["total_usd"] == float(sum(range(1, 13)))


@pytest.mark.parametrize("client_name, operation, call", [
    ("cloudwatch", "describe_alarms", "get_alarm_state"),
    ("ec2", "describe_instances", "get_ec2_inventory"),
    ("ce", "get_cost_and_usage", "get_yesterday_spend"),
])
def test_access_denied_is_raised_not_swallowed(client_name, operation, call):
    """The first cloud invoke failed with AccessDenied on all three tools.

    The collectors must let that error through so the agent reports it. A
    collector that caught it and returned an empty list would turn "I am not
    allowed to look" into "there is nothing there".
    """
    client = getattr(collectors, client_name)
    with Stubber(client) as stub:
        stub.add_client_error(operation, service_error_code="AccessDeniedException",
                              http_status_code=403)
        with pytest.raises(ClientError) as err:
            getattr(collectors, call)()

    assert err.value.response["Error"]["Code"] == "AccessDeniedException"
