## Metadata

* **Smell name:** nested_forms
* **Expected smell location:** Function `authenticate-request`
* **Affected forms:** `if-let`
* **Short explanation:** Nested if-lets that can be combined (e.g., using a single let or a macro like some->) to avoid rightward drift.

```Clojure
(ns web.auth)

(defn authenticate-request [request]
  ; VALIDATION: SMELL START - nested_forms
  ; VALIDATION: Nested if-lets cause unnecessary rightward drift
  (if-let [header (get-in request [:headers "authorization"])]
    (if-let [token (extract-token header)]
      (if-let [user (verify-token token)]
        {:status 200 :body user}
        {:status 401 :body "Invalid token"})
      {:status 401 :body "Malformed authorization header"})
    {:status 401 :body "Missing authorization header"}))
  ; VALIDATION: SMELL END
```
