"""
Admin utilities module for the Real-Time Online Interview system.
Handles data processing and calculations for the admin dashboard.
"""

from models.user_model import User


def calculate_admin_stats(users):
    """
    Calculate statistics for the admin dashboard.

    Args:
        users: List of User objects

    Returns:
        dict: {
            'total_candidates': int,
            'selected': int,
            'rejected': int,
            'average_score': float
        }
    """
    total_candidates = len(users)
    selected = 0
    rejected = 0
    total_score_sum = 0
    total_attempts = 0

    for u in users:
        try:
            if u.is_selected():
                selected += 1
            else:
                rejected += 1

            # Score summary across all users (defaults: 0 if none)
            total_score_sum += (
                (u.aptitude_score or 0)
                + (u.technical_score or 0)
                + (u.coding_score or 0)
                + (u.hr_score or 0)
            )
            total_attempts += 1
        except Exception:
            rejected += 1

    average_score = (
        round(total_score_sum / total_attempts, 1) if total_attempts > 0 else 0
    )

    return {
        "total_candidates": total_candidates,
        "selected": selected,
        "rejected": rejected,
        "average_score": average_score,
    }


def get_chart_data(selected, rejected):
    """
    Prepare chart data for Chart.js.

    Args:
        selected: Number of selected candidates
        rejected: Number of rejected candidates

    Returns:
        dict: Chart.js compatible data structure
    """
    return {
        "labels": ["Selected", "Rejected"],
        "datasets": [
            {
                "label": "Candidates",
                "data": [selected, rejected],
                "backgroundColor": ["#2ecc71", "#e74c3c"],
            }
        ],
    }


def export_candidates_to_excel(users):
    """
    Generate Excel-compatible HTML table for candidate export.

    Args:
        users: List of User objects

    Returns:
        str: HTML table string
    """
    table_html = """
    <table border="1">
    <thead>
    <tr>
    <th>ID</th>
    <th>Name</th>
    <th>Email</th>
    <th>Phone</th>
    <th>Aptitude</th>
    <th>Technical</th>
    <th>Coding</th>
    <th>HR</th>
    <th>Status</th>
    </tr>
    </thead>
    <tbody>
    """

    for user in users:
        status = "Completed" if user.hr_done else "In Progress"
        table_html += f"""
        <tr>
        <td>{user.id}</td>
        <td>{user.name}</td>
        <td>{user.email}</td>
        <td>{user.phone or ""}</td>
        <td>{user.aptitude_score or 0}</td>
        <td>{user.technical_score or 0}</td>
        <td>{user.coding_score or 0}</td>
        <td>{user.hr_score or 0}</td>
        <td>{status}</td>
        </tr>
        """

    table_html += "</tbody></table>"
    return table_html


def filter_candidates(users, search_term="", status_filter="all"):
    """
    Filter candidates based on search term and status.

    Args:
        users: List of User objects
        search_term: String to search in names
        status_filter: "all", "completed", or "in-progress"

    Returns:
        list: Filtered list of User objects
    """
    filtered = []

    for user in users:
        name_match = search_term.lower() in user.name.lower() if search_term else True

        status = "completed" if user.hr_done else "in-progress"
        status_match = (status_filter == "all") or (status_filter == status)

        if name_match and status_match:
            filtered.append(user)

    return filtered


def sort_candidates(users, sort_by="id", order="asc"):
    """
    Sort candidates by specified field.

    Args:
        users: List of User objects
        sort_by: Field to sort by ("id", "name", "email", etc.)
        order: "asc" or "desc"

    Returns:
        list: Sorted list of User objects
    """
    reverse = order == "desc"

    if sort_by == "id":
        return sorted(users, key=lambda u: u.id, reverse=reverse)
    elif sort_by == "name":
        return sorted(users, key=lambda u: u.name.lower(), reverse=reverse)
    elif sort_by == "email":
        return sorted(users, key=lambda u: u.email.lower(), reverse=reverse)
    elif sort_by == "aptitude":
        return sorted(users, key=lambda u: u.aptitude_score or 0, reverse=reverse)
    elif sort_by == "technical":
        return sorted(users, key=lambda u: u.technical_score or 0, reverse=reverse)
    elif sort_by == "coding":
        return sorted(users, key=lambda u: u.coding_score or 0, reverse=reverse)
    elif sort_by == "hr":
        return sorted(users, key=lambda u: u.hr_score or 0, reverse=reverse)
    else:
        return users
