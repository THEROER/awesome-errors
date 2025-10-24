"""
Example of handling HTTPException with passing detail to the details field.
"""

from fastapi import FastAPI, HTTPException
from awesome_errors import setup_error_handling

app = FastAPI()

# Налаштування обробки помилок
setup_error_handling(app, debug=False)


@app.get("/users/{user_id}")
def get_user(user_id: int):
    """Example endpoint that raises HTTPException."""
    if user_id == 404:
        raise HTTPException(
            status_code=404,
            detail="User with ID 404 not found in the system",
        )

    if user_id == 403:
        raise HTTPException(
            status_code=403,
            detail="Access denied for user with ID 403",
        )

    if user_id == 400:
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID format",
        )

    return {"id": user_id, "name": "John Doe", "email": "john@example.com"}


@app.get("/admin/users/{user_id}")
def get_admin_user(user_id: int):
    """Приклад endpoint з детальною інформацією про помилку."""
    if user_id == 999:
        raise HTTPException(
            status_code=418,
            detail="I'm a teapot and can't process this request",
        )

    return {"id": user_id, "role": "admin", "permissions": ["read", "write"]}


if __name__ == "__main__":
    import uvicorn  # type: ignore

    uvicorn.run(app, host="0.0.0.0", port=8000)
