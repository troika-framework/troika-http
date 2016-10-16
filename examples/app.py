import logging

from troika import http


class RequestHandler(http.RequestHandler):

    def get(self, *args, **kwargs):
        self.finish({
            'hello': {
                'world': {
                    'foo': 'bar',
                    'baz': 'qux',
                    'corgie': [
                        'one', 'two', 'three'
                    ]
                }
            }
        })

    def post(self, *args, **kwargs):
        self.logger.debug('Request Body: %r', self.get_body_arguments())
        self.set_status(204)
        self.finish()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    application = http.Application([
        ('/', RequestHandler),
        ('/google', http.RedirectHandler, {'url': 'https://www.google.com'})
    ], {
        'serve_traceback': True,
        'default_content_type': 'application/json'
    })
    application.run()
