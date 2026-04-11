"""
Authentication information extraction from OpenAPI spec.

Implements: getAuthInfo (S11)
"""

from typing import Dict, Any, List


def get_auth_info() -> Dict[str, Any]:
    """
    Extract authentication requirements from OpenAPI spec.

    Returns:
        {
            "required": bool,
            "global": {
                "required": bool,
                "schemes": ["scheme_name"]
            },
            "schemes": [
                {
                    "name": "api_key",
                    "type": "apiKey",
                    "in": "header|query|cookie",
                    "paramName": "X-API-Key",
                    ...
                }
            ],
            "endpoints": {
                "/users": {
                    "overrides": bool,
                    "required": bool,
                    "schemes": ["bearer"]
                }
            }
        }
    """
    from core.spec_store import get_store

    spec_store = get_store()
    spec = spec_store.get_spec()

    if not spec:
        return {"required": False, "global": {}, "schemes": [], "endpoints": {}}

    result = {
        "required": False,
        "global": {"required": False, "schemes": []},
        "schemes": [],
        "endpoints": {},
    }

    # Extract security schemes from components
    components = spec.get("components", {})
    security_schemes = components.get("securitySchemes", {})

    # Parse each security scheme
    for scheme_name, scheme_def in security_schemes.items():
        result["schemes"].append(_parse_security_scheme(scheme_name, scheme_def))

    # Get global security requirements
    global_security = spec.get("security", [])
    if global_security:
        result["required"] = True
        result["global"]["required"] = True
        for sec_req in global_security:
            for scheme_name in sec_req.keys():
                if scheme_name not in result["global"]["schemes"]:
                    result["global"]["schemes"].append(scheme_name)

    # Get per-endpoint security overrides
    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() in [
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "head",
                "options",
            ]:
                endpoint_security = operation.get("security")
                if endpoint_security is not None:
                    endpoint_key = path
                    if endpoint_key not in result["endpoints"]:
                        result["endpoints"][endpoint_key] = {}

                    result["endpoints"][endpoint_key]["overrides"] = True
                    result["endpoints"][endpoint_key]["required"] = len(endpoint_security) > 0

                    schemes = []
                    for sec_req in endpoint_security:
                        for scheme_name in sec_req.keys():
                            if scheme_name not in schemes:
                                schemes.append(scheme_name)
                    result["endpoints"][endpoint_key]["schemes"] = schemes

    return result


def _parse_security_scheme(name: str, scheme_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a single security scheme definition.

    Args:
        name: Scheme name
        scheme_def: Scheme definition from OpenAPI spec

    Returns:
        Dict with parsed scheme information
    """
    result = {
        "name": name,
        "type": scheme_def.get("type"),  # apiKey, http, oauth2, openIdConnect
    }

    # Common fields
    if "description" in scheme_def:
        result["description"] = scheme_def["description"]

    # API Key specific
    if scheme_def.get("type") == "apiKey":
        result["in"] = scheme_def.get("in")  # header, query, cookie
        result["paramName"] = scheme_def.get("name")

    # HTTP specific
    elif scheme_def.get("type") == "http":
        result["scheme"] = scheme_def.get("scheme")  # bearer, basic
        if "bearerFormat" in scheme_def:
            result["bearerFormat"] = scheme_def["bearerFormat"]

    # OAuth2 specific
    elif scheme_def.get("type") == "oauth2":
        flows = scheme_def.get("flows", {})
        result["flows"] = {}

        for flow_name, flow_def in flows.items():
            result["flows"][flow_name] = {
                "authorizationUrl": flow_def.get("authorizationUrl"),
                "tokenUrl": flow_def.get("tokenUrl"),
                "refreshUrl": flow_def.get("refreshUrl"),
                "scopes": list(flow_def.get("scopes", {}).keys()),
            }

        # Get scopes from all flows
        all_scopes = set()
        for flow_def in flows.values():
            all_scopes.update(flow_def.get("scopes", {}).keys())
        if all_scopes:
            result["scopes"] = list(all_scopes)

    # OpenID Connect specific
    elif scheme_def.get("type") == "openIdConnect":
        result["openIdConnectUrl"] = scheme_def.get("openIdConnectUrl")

    return result
