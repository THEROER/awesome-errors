"""
FastAPI automatic error documentation integration.
Automatically analyzes routes and adds error response schemas to OpenAPI docs.
"""

import logging

logger = logging.getLogger(__name__)


def auto_analyze_errors(func):
    from ..analysis.decorators import analyze_errors

    decorated_func = analyze_errors()(func)
    decorated_func._auto_openapi = True
    return decorated_func


def setup_automatic_error_docs(app, **kwargs):
    """
    Setup automatic error documentation for all FastAPI routes.

    This function analyzes all route functions using AST analysis to find
    possible errors and automatically adds comprehensive error response
    schemas to the OpenAPI documentation.

    Args:
        app: FastAPI application instance
        **kwargs: Additional configuration options
            - include_http_exceptions: Whether to analyze HTTPException (default: True)
            - max_depth: Maximum analysis depth for function calls (default: 3)
            - exclude_paths: List of path patterns to exclude from analysis
    """
    try:
        from fastapi import FastAPI

        if not isinstance(app, FastAPI):
            logger.warning("setup_automatic_error_docs expects a FastAPI app instance")
            return

        logger.info("Setting up automatic error documentation for FastAPI routes...")

        # Apply to all routes in the app
        _apply_auto_error_docs_to_app(app, **kwargs)

        logger.info("Automatic error documentation setup complete")

    except ImportError:
        logger.warning("FastAPI not available, skipping automatic error documentation")
    except Exception as e:
        logger.error(f"Failed to setup automatic error documentation: {e}")


def _apply_auto_error_docs_to_app(app, **kwargs):
    """Apply automatic error documentation to all routes in FastAPI app."""
    from ..analysis.error_analyzer import ErrorAnalyzer
    from ..analysis.decorators import _generate_openapi_responses

    exclude_paths = kwargs.get("exclude_paths", [])
    max_depth = kwargs.get("max_depth", 3)

    routes_processed = 0
    errors_found = 0

    for route in app.routes:
        # Skip if path is in exclude list
        if any(pattern in route.path for pattern in exclude_paths):
            continue

        if hasattr(route, "endpoint") and hasattr(route, "methods"):
            try:
                endpoint_func = route.endpoint

                # Analyze the function for possible errors
                analyzer = ErrorAnalyzer(
                    endpoint_func, max_depth=max_depth, analyze_decorators=True
                )
                analysis = analyzer.analyze()
                error_codes = analysis.get("error_codes", set())

                if error_codes:
                    # Generate OpenAPI responses
                    openapi_responses = _generate_openapi_responses(error_codes, {})

                    # Apply responses to the route
                    if not hasattr(route, "responses"):
                        route.responses = {}

                    # Merge with existing responses (don't overwrite existing)
                    for status_code, response_schema in openapi_responses.items():
                        if status_code not in route.responses:
                            route.responses[status_code] = response_schema

                    routes_processed += 1
                    errors_found += len(error_codes)

                    logger.debug(
                        f"Applied error responses to {route.path} "
                        f"({', '.join(route.methods)}): {list(openapi_responses.keys())}"
                    )

            except Exception as e:
                logger.warning(f"Failed to analyze errors for route {route.path}: {e}")

        # Also handle included routers
        elif hasattr(route, "app") and hasattr(route.app, "routes"):
            _process_sub_routes(route.app.routes, exclude_paths, max_depth)

    logger.info(
        f"Processed {routes_processed} routes, found {errors_found} total error codes"
    )


def _process_sub_routes(routes, exclude_paths, max_depth):
    """Process routes in sub-applications/routers."""
    from ..analysis.error_analyzer import ErrorAnalyzer
    from ..analysis.decorators import _generate_openapi_responses

    for sub_route in routes:
        # Skip if path is in exclude list
        if any(pattern in sub_route.path for pattern in exclude_paths):
            continue

        if hasattr(sub_route, "endpoint") and hasattr(sub_route, "methods"):
            try:
                endpoint_func = sub_route.endpoint

                analyzer = ErrorAnalyzer(
                    endpoint_func, max_depth=max_depth, analyze_decorators=True
                )
                analysis = analyzer.analyze()
                error_codes = analysis.get("error_codes", set())

                if error_codes:
                    openapi_responses = _generate_openapi_responses(error_codes, {})

                    if not hasattr(sub_route, "responses"):
                        sub_route.responses = {}

                    # Merge with existing responses
                    for status_code, response_schema in openapi_responses.items():
                        if status_code not in sub_route.responses:
                            sub_route.responses[status_code] = response_schema

                    logger.debug(
                        f"Applied error responses to sub-route {sub_route.path}: "
                        f"{list(openapi_responses.keys())}"
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to analyze errors for sub-route {sub_route.path}: {e}"
                )


def apply_auto_error_docs_to_router(router, **kwargs):
    """
    Apply automatic error documentation to a specific FastAPI router.

    Args:
        router: FastAPI APIRouter instance
        **kwargs: Configuration options (same as setup_automatic_error_docs)
    """
    try:
        from fastapi import APIRouter

        if not isinstance(router, APIRouter):
            logger.warning(
                "apply_auto_error_docs_to_router expects an APIRouter instance"
            )
            return

        _apply_auto_error_docs_to_routes(router.routes, **kwargs)

    except ImportError:
        logger.warning("FastAPI not available for router error documentation")
    except Exception as e:
        logger.error(f"Failed to apply error docs to router: {e}")


def _apply_auto_error_docs_to_routes(routes, **kwargs):
    """Apply automatic error documentation to a list of routes."""
    from ..analysis.error_analyzer import ErrorAnalyzer
    from ..analysis.decorators import _generate_openapi_responses

    exclude_paths = kwargs.get("exclude_paths", [])
    max_depth = kwargs.get("max_depth", 3)

    for route in routes:
        # Skip if path is in exclude list
        if any(pattern in route.path for pattern in exclude_paths):
            continue

        if hasattr(route, "endpoint") and hasattr(route, "methods"):
            try:
                endpoint_func = route.endpoint

                analyzer = ErrorAnalyzer(
                    endpoint_func, max_depth=max_depth, analyze_decorators=True
                )
                analysis = analyzer.analyze()
                error_codes = analysis.get("error_codes", set())

                if error_codes:
                    openapi_responses = _generate_openapi_responses(error_codes, {})

                    if not hasattr(route, "responses"):
                        route.responses = {}

                    # Merge with existing responses
                    for status_code, response_schema in openapi_responses.items():
                        if status_code not in route.responses:
                            route.responses[status_code] = response_schema

                    logger.debug(
                        f"Applied error responses to {route.path}: {list(openapi_responses.keys())}"
                    )

            except Exception as e:
                logger.warning(f"Failed to analyze errors for route {route.path}: {e}")
