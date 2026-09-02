# To be implemented in Repository: "run-confluence-locally":
# Modification in existing file:
# confluence/utils/module_names.py




# get_repo_name("qq") returns "qq" (lowercase),
# but the GitHub repository is SWOT-Confluence/QQ (uppercase).
# The _clone_worker in module_images.py uses get_repo_name(name) to form the git clone URL:

# url = f"https://github.com/{github_name}/{repo_name}.git"

# With repo_name = "qq", the clone would target SWOT-Confluence/qq.git,
# which does not exist. GitHub clone will fail silently or with a 404.

# one entry must be added to REPO_NAME_MAP:

REPO_NAME_MAP = {
    "offline": "offline-discharge-data-product-creation",
    "moi": "MOI",
    "validation": "Validation",
    "hivdi": "h2ivdi",
    "busboi": "BUSBOI",
    "lakeflow": "LakeFlow_Confluence",
    "qq": "QQ",
}


# No change to IMAGE_NAME_MAP is needed — the SIF and image will be named qq (lowercase), which is correct and consistent with the {{ sif_dir }}/qq.sif reference in the template above.






