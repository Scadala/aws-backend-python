function bookmarkDropDown(element) {
    fetch(element.dataset.url, {
      method: element.dataset.method,
      headers: {
        "Content-type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ library: element.dataset.library }),
    });
    if (element.dataset.method == "DELETE") {
      element.dataset.method = "PUT";
      element.classList.remove("text-bg-success");
    } else {
      element.dataset.method = "DELETE";
      element.classList.add("text-bg-success");
    }
    btnGroup = element.closest("div.btn-group");
    hasSuccessClass = Array.from(btnGroup.querySelectorAll("ul > li > a")).some(
      (link) => link.classList.contains("text-bg-success")
    );
    if (hasSuccessClass) {
      btnGroup
        .querySelectorAll("a")
        .forEach((link) => link.classList.add("btn-success"));
    } else {
      btnGroup
        .querySelectorAll("a")
        .forEach((link) => link.classList.remove("btn-success"));
    }
  }