USER_REPO_EXIST_QUERY = """
query ($owner: String!, $repository: String!) {
    repository(owner: $owner, name: $repository){
        name
    }
}
"""

TOKEN_TEST_QUERY = "query {viewer {login}}"