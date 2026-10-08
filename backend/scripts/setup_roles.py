"""Create the CampusPulse Cognito groups and assign users to them.

The user pool predates the Terraform code, so its groups are managed here.
The script is idempotent: existing groups are left untouched.

    COGNITO_USER_POOL_ID=eu-north-1_xxx python setup_roles.py
    COGNITO_USER_POOL_ID=eu-north-1_xxx python setup_roles.py --user staff@campus.edu --group Staff
"""
import argparse
import os

import boto3

GROUPS = {
    "Admin": (1, "Full access: dashboard, alerts and the IoT simulator (POST /events)"),
    "Staff": (2, "Read-only operations role: dashboard, GET /stats, /events, /alerts"),
    "Sensor": (3, "Machine accounts for IoT devices: POST /events only"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", help="username (email) to add to a group")
    parser.add_argument("--group", choices=GROUPS, help="group to add the user to")
    args = parser.parse_args()

    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    client = boto3.client("cognito-idp", region_name=os.environ.get("AWS_DEFAULT_REGION", "eu-north-1"))

    existing = {g["GroupName"] for g in client.list_groups(UserPoolId=pool_id)["Groups"]}
    for name, (precedence, description) in GROUPS.items():
        if name in existing:
            print(f"= group {name} already exists")
            continue
        client.create_group(UserPoolId=pool_id, GroupName=name, Precedence=precedence, Description=description)
        print(f"+ created group {name}")

    if args.user and args.group:
        client.admin_add_user_to_group(UserPoolId=pool_id, Username=args.user, GroupName=args.group)
        print(f"+ added {args.user} to {args.group}")


if __name__ == "__main__":
    main()
