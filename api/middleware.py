
import logging
import time


logger = logging.getLogger(__name__)


class ExpenseRequestLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        start_time = time.perf_counter()

        response = self.get_response(request)
#  Think of self.get_response(request) as:
# "I'm done with my request-side processing. Pass this request onward, then give me the response when the remaining processing is finished."

# And remember: if middleware returns a response without calling self.get_response(request), it stops the request from reaching subsequent middleware layers and the view.

        duration = (time.perf_counter() - start_time) * 1000

        if request.path.startswith("/expenses/"):
            logger.info(
                "%s %s - %s - %.2f ms",
                request.method,
                request.path,
                response.status_code,
                duration,
            )

        # 4. Add a custom header to the response
        response["X-Response-Time"] = f"{duration:.2f}ms"

        return response
